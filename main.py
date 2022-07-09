# This is a sample Python script.
import pandas as pd
import json
import geopy
import geopy.distance
import plotly.figure_factory as ff
import numpy as np
import pandas as pd

# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.

def load_population_data(filename):
    df = pd.read_csv(filename, index_col=False)
    df['CTYNAME'] = df['CTYNAME'].str.split(expand=True)[0]

    column_mappings = {
        'COUNTY': 'county_id',
        'STATE': 'state_id',
        #    'CTYNAME': 'county_name',
        #   'STNAME': 'state_name',
        'POPESTIMATE2020': 'pop_2020',
    }
    df.rename(columns=column_mappings, inplace=True)
    population_df = df[df['county_id'] != 0][list(column_mappings.values())]

    population_df['State FIPS Code'] = population_df['state_id'].apply(lambda x: str(x).zfill(2))
    population_df['County FIPS Code'] = population_df['county_id'].apply(lambda x: str(x).zfill(3))
    population_df['FIPS'] = population_df['State FIPS Code'] + population_df['County FIPS Code']
    population_df.set_index(['state_id', 'county_id'], inplace=True)

    return population_df


def load_stadium_data(filename):
    team_data = {
        'team': [],
        'conference': [],
        'location': []
    }

    with open(filename) as file:
        json_data = json.load(file)
        for team in json_data['features']:
            team_prop = team['properties']
            team_geo = team['geometry']['coordinates']
            team_data['team'].append(team_prop['Team'])
            team_data['conference'].append(team_prop['Conference'])
            team_data['location'].append(geopy.Point(latitude=team_geo[1], longitude=team_geo[0]))

    df = pd.DataFrame(team_data)
    df.set_index('team', inplace=True)
    return df


def cache_county_geo_center_data():
    # this file is very large due to county boundary data.
    # however, the geo center of each county is in it too which is what we want
    filename = 'us-county-boundaries.csv'
    # https://public.opendatasoft.com/explore/dataset/us-county-boundaries/download/?format=csv&timezone=America/New_York&lang=en&use_labels_for_header=true&csv_separator=%3B

    df = pd.read_csv(filename, delimiter=';')

    column_mappings = {
        'NAME': 'county_name',
        'STATE_NAME': 'state_name',
        'STATEFP': 'state_id',
        'COUNTYFP': 'county_id',
        'location': 'geo_center',
    }

    df['location'] = df.apply(lambda row: geopy.Point(*row['Geo Point'].split(',')), axis=1)
    # df['location'] = df.apply(lambda row: foo(row))
    df.rename(columns=column_mappings, inplace=True)

    # drop all columns except the ones we need
    df = df[list(column_mappings.values())]
    df.set_index(['state_id', 'county_id'], inplace=True)
    df.to_csv('county_geo_center.csv')


def load_team_colors(filename):
    df = pd.read_csv(filename, delimiter="\t")
    df.set_index(['team'],inplace=True)

    return df



def create_closest_team_cache():

    print("loading county population data")
    population_df = load_population_data('county_population.csv')
    print("loading county geo centers")
    county_df = pd.read_csv('county_geo_center.csv', index_col=['state_id', 'county_id'])
    print("creating county dataframe")
    county_df = pd.merge(county_df, population_df, how='inner', left_index=True, right_index=True)
    print("loading team stadium locations")
    team_df = load_stadium_data('stadiums.json')
    print("loading team colors")
    # colors from here: https://teamcolorcodes.com/nfl-team-color-codes/
    # replace some teams' primary color with secondary to make map look good
    team_color_df = load_team_colors('team_colors.dat')
    print("creating team dataframe")
    team_df = pd.merge(team_df, team_color_df, how='inner', left_index=True, right_index=True)



    def find_closest_team(county_row):
        county_distances_to_each_team = team_df.apply(
            lambda team_row: geopy.distance.distance(county_row['geo_center'], team_row['location']).miles, axis=1)

        closest_team = county_distances_to_each_team.idxmin()

        closest_team_distance = county_distances_to_each_team.loc[closest_team]

        closest_team_id = team_df.loc[closest_team].get('team_id')
        s = pd.Series([closest_team, closest_team_distance, closest_team_id])

        return s

    print("calculating closest stadium for each county")
    county_df[['closest_team', 'closest_team_distance','closest_team_id']] = county_df.apply(find_closest_team, axis=1)

    print("saving data to file")
    county_df.to_csv('closest_team_to_each_county.csv')


def show_nfl_map():
    df_sample = pd.read_csv('closest_team_to_each_county.csv')
    df_colors = pd.read_csv('team_colors.dat',delimiter="\t")

    colorscale = df_colors['hex'].tolist()
    # you have to have one extra color scale for it to work
    # have not dug into why this is yet
    colorscale.append("#ffffff")

    # makes a list from 1 to 32
    endpts = list(np.linspace(1, 32, len(colorscale) -1 ))

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



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    create_closest_team_cache()

    show_nfl_map()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
