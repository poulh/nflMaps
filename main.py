# This is a sample Python script.
import pandas as pd
import json
import geopy
import geopy.distance
import plotly.figure_factory as ff
import numpy as np
import logging


# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.

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

    df_population['State FIPS Code'] = df_population['state_code'].apply(lambda x: str(x).zfill(2))
    df_population['County FIPS Code'] = df_population['county_code'].apply(lambda x: str(x).zfill(3))
    df_population['FIPS'] = df_population['State FIPS Code'] + df_population['County FIPS Code']
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
    # df['location'] = df.apply(lambda row: foo(row))
    df.rename(columns=column_mappings, inplace=True)

    # drop all columns except the ones we need
    df = df[list(column_mappings.values())]
    df.set_index(['state_code', 'county_code'], inplace=True)
    df.to_csv('county_geo_center.csv')


def create_team_data_cache():
    logging.info("loading team stadium locations")
    df_stadium = load_stadium_data('stadiums.json')
    logging.info("loading team colors")
    # colors from here: https://teamcolorcodes.com/nfl-team-color-codes/
    # replace some teams' primary color with secondary to make map look good
    df_team_color = pd.read_csv('team_colors.dat', delimiter="\t", index_col=['team_name'])
    logging.info("creating team dataframe")
    df_stadium = pd.merge(df_stadium, df_team_color, how='outer', left_index=True, right_index=True)
    df_stadium = df_stadium.reset_index()
    df_stadium['team_id'] = df_stadium['team_id'].fillna(-1)

    df_stadium = df_stadium.astype({'team_id': int})
    df_stadium = df_stadium.set_index('team_id')
    df_stadium.to_csv('team_data.csv')


def create_closest_team_cache():
    logging.info("loading county population data")
    population_df = load_population_data('county_population.csv')
    logging.info("loading county geo centers")
    county_df = pd.read_csv('county_geo_center.csv', index_col=['state_code', 'county_code'])
    logging.info("creating county dataframe")
    county_df = pd.merge(county_df, population_df, how='inner', left_index=True, right_index=True)
    team_df = pd.read_csv('team_data.csv', index_col=['team_name'])
    team_df = team_df[team_df['team_id'] != -1]

    def calculate_closest_team(county_row):
        county_distances_to_each_team = team_df.apply(
            lambda team_row: geopy.distance.distance(county_row['geo_center'], team_row['stadium_location']).miles,
            axis=1)

        closest_team = county_distances_to_each_team.idxmin()
        closest_team_distance = county_distances_to_each_team.loc[closest_team]
        closest_team_id = team_df.loc[closest_team].get('team_id')
        s = pd.Series([closest_team, closest_team_distance, closest_team_id])

        return s

    logging.info("calculating closest stadium for each county")
    county_df[['closest_team', 'closest_team_distance', 'closest_team_id']] = county_df.apply(calculate_closest_team,
                                                                                              axis=1)

    logging.info("saving data to file")
    county_df.to_csv('closest_team_to_each_county.csv')


def show_nfl_map():
    df_sample = pd.read_csv('closest_team_to_each_county.csv')
    df_colors = pd.read_csv('team_colors.dat', delimiter="\t")

    colorscale = df_colors['team_color_hex'].tolist()
    # you have to have one extra color scale for it to work
    # have not dug into why this is yet
    colorscale.append("#ffffff")

    # makes a list from 1 to 32
    endpts = list(np.linspace(1, 32, len(colorscale) - 1))

    fips = df_sample['FIPS'].tolist()
    values = df_sample['closest_team_id'].tolist()

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
    logging.basicConfig()

    create_team_data_cache()
    create_closest_team_cache()

    show_nfl_map()
