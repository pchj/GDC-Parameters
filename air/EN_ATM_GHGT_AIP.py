import aiohttp
import json
import pandas as pd
import plotly.graph_objects as go
import sys
import os
from datetime import datetime
import dash
from dash import dcc, html
import nest_asyncio
import asyncio

nest_asyncio.apply()

async def fetch_data(session, url, params):
    try:
        async with session.get(url, params=params) as response:
            return await response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

async def parse_country_data(session, country_codes):
    country_data = []
    url = 'https://api.datacommons.org/stat/series'
    tasks = [fetch_data(session, url, {'place': f'country/{code}', 'stat_var': 'sdg/EN_ATM_GHGT_AIP'}) for code in country_codes]

    responses = await asyncio.gather(*tasks)

    for code, response in zip(country_codes, responses):
        if response and 'series' in response:
            country_data.append({
                "country_code": code,
                "data": [{"year": year, "emission": value} for year, value in sorted(response['series'].items())]
            })
        else:
            print(f'No data available for {code}.')

    return country_data

async def fetch_eu_data(session):
    url = 'https://api.datacommons.org/stat/series'
    params = {'place': 'undata-geo/G00500360', 'stat_var': 'sdg/EN_ATM_GHGT_AIP'}

    try:
        async with session.get(url, params=params) as response:
            eu_data = await response.json()
            if 'series' in eu_data:
                EU_data = [{"country_code": "EU", "data": [{"year": year, "emission": value} for year, value in sorted(eu_data['series'].items())]}]
                print(f'Data fetched for European Union:', EU_data)
                return EU_data
            else:
                print("No EU data available.")
                return []
    except Exception as e:
        print(f"Error fetching EU data: {e}")
        return []

async def save_data_to_json(data, file_path):
    try:
        with open(file_path, 'w') as json_file:
            json.dump(data, json_file, indent=4)
        print(f'Data saved to {file_path}')
    except Exception as e:
        print(f"Error saving data to JSON: {e}")

async def load_data_from_json(file_path):
    try:
        with open(file_path, 'r') as json_file:
            data = json.load(json_file)
        return data
    except Exception as e:
        print(f"Error loading data from JSON: {e}")
        return []

def plot_data(combined_data, graph_type):
    fig = go.Figure()

    if graph_type == 'line':
        for country in combined_data:
            fig.add_trace(go.Scatter(x=[item['year'] for item in country['data']],
                                     y=[item['emission'] for item in country['data']],
                                     mode='lines+markers',
                                     name=country['country_code']))
    elif graph_type == 'bar':
        for country in combined_data:
            fig.add_trace(go.Bar(x=[item['year'] for item in country['data']],
                                 y=[item['emission'] for item in country['data']],
                                 name=country['country_code']))
    elif graph_type == 'pie':
        fig = go.Figure(data=[go.Pie(labels=[country['country_code'] for country in combined_data],
                                     values=[sum([item['emission'] for item in country['data']]) for country in combined_data])])
    elif graph_type == 'stacked':
        years = sorted(list(set([item['year'] for country in combined_data for item in country['data']])))
        data_dict = {country['country_code']: [0] * len(years) for country in combined_data}
        for country in combined_data:
            for item in country['data']:
                data_dict[country['country_code']][years.index(item['year'])] += item['emission']
        fig = go.Figure()
        for country_code, emissions in data_dict.items():
            fig.add_trace(go.Bar(x=years, y=emissions, name=country_code))

    # Add more cases for other graph types here

    fig.update_layout(title='EN_ATM_GHGT_AIP Data',
                      xaxis_title='Year',
                      yaxis_title='Emission',
                      template='plotly_dark')

    return fig

async def main():
    country_codes = ['AUS', 'AUT', 'BEL', 'BGR', 'BLR', 'CAN', 'CHE', 'CYP', 'CZE', 'DEU',
                    'DNK', 'ESP', 'EST', 'FIN', 'FRA', 'GBR', 'GRC', 'HRV', 'HUN', 'IRL',
                    'ISL', 'ITA', 'JPN', 'LIE', 'LTU', 'LUX', 'LVA', 'MCO', 'MLT', 'NLD',
                    'NOR', 'NZL', 'POL', 'PRT', 'ROU', 'RUS', 'SVK', 'SVN', 'SWE', 'TUR',
                    'UKR', 'USA']
    file_name = "EN_ATM_GHGT_AIP_sorted.json"
    file_path = os.path.join(os.getcwd(), file_name)

    async with aiohttp.ClientSession() as session:
        country_data_task = parse_country_data(session, country_codes)
        eu_data_task = fetch_eu_data(session)

        country_data, EU_data = await asyncio.gather(country_data_task, eu_data_task)

        combined_data = country_data + EU_data if EU_data else country_data

        await save_data_to_json(combined_data, file_path)
        data_example = await load_data_from_json(file_path)
        json.dump({"EN_ATM_GHGT_AIP_Data": combined_data}, sys.stdout)

        df = pd.DataFrame([{'country_code': d['country_code'], 'year': item['year'], 'emission': item['emission']} for d in combined_data for item in d['data']])

        csv_file_path = os.path.join(os.getcwd(), 'EN_ATM_GHGT_AIP_Data.csv')
        df.to_csv(csv_file_path, index=False)
        print(f'Data saved to {csv_file_path}')

        app = dash.Dash(__name__)

        app.layout = html.Div([
            dcc.Dropdown(
                id='country-select',
                options=[{'label': country['country_code'], 'value': country['country_code']} for country in combined_data],
                value=['USA'],
                multi=True
            ),
            dcc.Dropdown(
                id='graph-type-select',
                options=[
                    {'label': 'Line Graph', 'value': 'line'},
                    {'label': 'Bar Chart', 'value': 'bar'},
                    {'label': 'Pie Chart', 'value': 'pie'},
                    {'label': 'Stacked Bar Chart', 'value': 'stacked'}
                    # Add more graph types here
                ],
                value='line'
            ),
            dcc.Graph(id='EN_ATM_GHGT_AIP_Data-graph')
        ])

        @app.callback(
            dash.dependencies.Output('EN_ATM_GHGT_AIP_Data-graph', 'figure'),
            [dash.dependencies.Input('country-select', 'value'),
             dash.dependencies.Input('graph-type-select', 'value')]
        )
        def update_graph(selected_countries, graph_type):
            selected_data = [country for country in combined_data if country['country_code'] in selected_countries]
            return plot_data(selected_data, graph_type)

        app.run_server(debug=True)

asyncio.run(main())
