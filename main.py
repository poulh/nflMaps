# This is a sample Python script.
import pandas as pd
import json
import geopy
import geopy.distance


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


def load_county_data(filename):
    df = pd.read_csv(filename, delimiter=';')

    column_mappings = {
        'NAME': 'county_name',
        'STATE_NAME': 'state_name',
        'STATEFP': 'state_id',
        'COUNTYFP': 'county_id',
        'location': 'location',
    }

    df['location'] = df.apply(lambda row: geopy.Point(*row['Geo Point'].split(',')), axis=1)
    # df['location'] = df.apply(lambda row: foo(row))
    df.rename(columns=column_mappings, inplace=True)
    df = df[list(column_mappings.values())]
    df.set_index(['state_id', 'county_id'], inplace=True)

    return df


def main():
    population_df = load_population_data('county_population.csv')
    team_df = load_stadium_data('stadiums.json')

    county_df = load_county_data('us-county-boundaries.csv')
    county_df = pd.merge(county_df, population_df, how='inner', left_index=True, right_index=True)

    def closest_team(county_row):
        county_distances_to_each_team = team_df.apply(
            lambda team_row: geopy.distance.distance(county_row['location'], team_row['location']).miles, axis=1)
        closest_team = county_distances_to_each_team.idxmin()
        closest_team_distance = county_distances_to_each_team.loc[closest_team]

        s = pd.Series([closest_team, closest_team_distance])
        return s

    # county_df[['closest_team','distance']] = county_df.apply(lambda county_row: closest_team(county_row), axis=1)
    county_df[['closest_team', 'closest_team_distance']] = county_df.apply(closest_team, axis=1)
    county_df.to_csv('county_info.csv')
    #team_pop_df = county_df.groupby('closest_team')['pop_2020'].sum()
    #print(team_pop_df)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
