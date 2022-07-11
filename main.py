# This is a sample Python script.
import pandas as pd
import json
import geopy
import geopy.distance
import plotly.figure_factory as ff
import numpy as np
import logging


def load_population_data(filename):
    df_population = pd.read_csv(filename, index_col=False)
    df_population['CTYNAME'] = df_population['CTYNAME'].str.split(expand=True)[0]

    column_mappings = {
        'COUNTY': 'county_code',
        'STATE': 'state_code',
        #    'CTYNAME': 'county_name',
        #   'STNAME': 'state_name',
        'POPESTIMATE2020': 'pop_2020',
    }
    df_population = df_population.rename(columns=column_mappings)
    df_population = df_population[df_population['county_code'] != 0][list(column_mappings.values())]

    df_population = df_population.set_index(['state_code', 'county_code'])

    return df_population


def load_stadium_data(filename):
    team_data = {
        'team_name': [],
        'team_conferences': [],
        'stadium_location': [],
        'stadium_name': []
    }

    with open(filename) as file:
        json_data = json.load(file)
        for team in json_data['features']:
            team_prop = team['properties']
            team_geo = team['geometry']['coordinates']
            team_data['team_name'].append(team_prop['Team'])
            team_data['team_conferences'].append(team_prop['Conference'])
            team_data['stadium_location'].append(geopy.Point(latitude=team_geo[1], longitude=team_geo[0]))
            team_data['stadium_name'].append(team_prop['Stadium'])

    df_stadium = pd.DataFrame(team_data)
    df_stadium = df_stadium.set_index('team_name')
    return df_stadium


def calculate_min_distance(ds_from, str_from_col, df_to_each, str_to_col):
    def calc_distance(ds_to):
        if ds_from['state_code'] == ds_to['closest_state_code']:
            return geopy.distance.distance(ds_from[str_from_col], ds_to[str_to_col]).miles / 2.5

        return geopy.distance.distance(ds_from[str_from_col], ds_to[str_to_col]).miles

    ds_distances_to_each = df_to_each.apply(calc_distance, axis=1)

    closest_index = ds_distances_to_each.idxmin()
    closest_distance = ds_distances_to_each.loc[closest_index]

    try:
        # if closest_index is a double or tuple index this code handles that.
        # splitting and putting one value in each column
        rval = list(closest_index)
    except TypeError as te:
        rval = [closest_index]
    rval.append(closest_distance)

    s = pd.Series(rval)

    return s


def create_county_geo_center_cache():
    # this file is very large due to county boundary data.
    # however, the geo center of each county is in it too which is what we want
    filename = 'us-county-boundaries.csv'
    # https://public.opendatasoft.com/explore/dataset/us-county-boundaries/download/?format=csv&timezone=America/New_York&lang=en&use_labels_for_header=true&csv_separator=%3B

    df = pd.read_csv(filename, delimiter=';')

    column_mappings = {
        'NAME': 'county_name',
        'STATE_NAME': 'state_name',
        'STATEFP': 'state_code',
        'COUNTYFP': 'county_code',
        'location': 'geo_center',
    }

    df['location'] = df.apply(lambda row: geopy.Point(*row['Geo Point'].split(',')), axis=1)
    df.rename(columns=column_mappings, inplace=True)

    # drop all columns except the ones we need
    df = df[list(column_mappings.values())]
    df.set_index(['state_code', 'county_code'], inplace=True)
    df.to_csv('county_geo_center.csv')


def create_team_data_cache():
    logging.info("loading team stadium locations")
    df_stadium = load_stadium_data('stadiums.json')

    # colors from here: https://teamcolorcodes.com/nfl-team-color-codes/
    # replaced some teams' primary color with secondary to make map look good
    logging.info("loading team colors")
    df_team_color = pd.read_csv('team_colors.dat', delimiter="\t", index_col=['team_name'])

    logging.info("creating team dataframe")
    df_stadium = pd.merge(df_stadium, df_team_color, how='inner', left_index=True, right_index=True)
    df_stadium = df_stadium.reset_index()

    logging.info("loading county geo centers")
    df_county = pd.read_csv('county_geo_center.csv', index_col=['state_code', 'county_code'])

    def calc_closest_county_to_each_stadium(ds_from):
        return calculate_min_distance(ds_from, 'stadium_location',
                                      df_county, 'geo_center')

    logging.info("calculating which county each stadium is in")
    columns_to_add = ['closest_state_code', 'closest_county_code', 'closest_county_distance']
    df_stadium[columns_to_add] = df_stadium.apply(calc_closest_county_to_each_stadium, axis=1)

    df_stadium = df_stadium.sort_values(by=['team_name'])
    logging.info("writing to file")
    df_stadium.to_csv('team_data.csv', index=False)


def create_closest_team_cache():
    logging.info("loading county population data")
    population_df = load_population_data('county_population.csv')
    logging.info("loading county geo centers")
    county_df = pd.read_csv('county_geo_center.csv', index_col=['state_code', 'county_code'])
    logging.info("creating county dataframe")
    county_df = pd.merge(county_df, population_df, how='inner', left_index=True, right_index=True)
    county_df = county_df.reset_index()
    team_df = pd.read_csv('team_data.csv')

    def calculate_closest_team(ds_from):
        return calculate_min_distance(ds_from, 'geo_center',
                                      team_df, 'stadium_location')

    logging.info("calculating closest stadium for each county")
    county_df[['closest_team_id', 'closest_team_distance']] = county_df.apply(calculate_closest_team,
                                                                              axis=1)
    logging.info("saving data to file")
    county_df.to_csv('closest_team_to_each_county.csv')


def show_nfl_map():
    df_counties = pd.read_csv('closest_team_to_each_county.csv')
    df_counties = df_counties.reset_index()
    df_counties['state_fips'] = df_counties['state_code'].apply(lambda x: str(x).zfill(2))
    df_counties['county_fips'] = df_counties['county_code'].apply(lambda x: str(x).zfill(3))
    df_counties['FIPS'] = df_counties['state_fips'] + df_counties['county_fips']
    # uncomment this to only color counties within X miles of the stadium
    df_counties.loc[df_counties['closest_team_distance'] > 125, 'closest_team_id'] = 32

    df_teams = pd.read_csv('team_data.csv')

    colorscale = df_teams['team_color_hex'].tolist()
    # you have to have one extra color scale for it to work
    # have not dug into why this is yet
    colorscale.append("#ffffff")

    # makes a list from 0 to 31; team IDs are zero based
    endpts = list(np.linspace(0, 31, len(colorscale) - 1))

    fips = df_counties['FIPS'].tolist()
    values = df_counties['closest_team_id'].tolist()

    fig = ff.create_choropleth(
        fips=fips, values=values,
        binning_endpoints=endpts,
        colorscale=colorscale,
        show_state_data=True,
        show_hover=True, centroid_marker={'opacity': 0},
        asp=2.9, title='The Closest NFL Team For Every County',
        legend_title='Team Colors'
    )

    fig.layout.template = None
    fig.show()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # create_team_data_cache()
    create_closest_team_cache()

    show_nfl_map()
