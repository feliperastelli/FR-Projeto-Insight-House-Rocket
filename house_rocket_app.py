import pandas as pd
import streamlit as st
import numpy as np
from streamlit_folium import folium_static
import folium
from folium.plugins import MarkerCluster
import geopandas
import plotly.express as px
from datetime import datetime

pd.set_option('display.float_format', lambda x: '%.2f' % x)

@st.cache(allow_output_mutation=True)
def get_data(path):
    data = pd.read_csv(path)

    return data

@st.cache(allow_output_mutation=True)
def get_geofile(url):
     geofile = geopandas.read_file(url)

     return geofile

def clean_data(data):
    # transformar formato da data
    data['date'] = pd.to_datetime(data['date']).dt.strftime('%Y-%m-%d')
    # Deletando os ID's repetidos, deixando o último cadastrado
    data = data.drop_duplicates(subset=['id'], keep='last')
    # Removendo imóvel com suposto erro de digitação no atributo 'bedrooms'
    data.drop(data.loc[data['bedrooms'] == 33].index, inplace=True)
    #transformando formato da coluna 'waterfront'
    data['waterfront'] = data['waterfront'].astype(str)

    return data

def set_feature(data):
    # Ano de construção: >< 1955
    data['constrution'] = data['yr_built'].apply(lambda x: '> 1955' if x > 1955
    else '< 1955')

    # Reforma
    data['renovated'] = data['yr_renovated'].apply(lambda x: 'no' if x == 0
    else 'yes')

    # Imoveis com porão ou sem porão
    data['basement'] = data['sqft_basement'].apply(lambda x: 'no' if x == 0
    else 'yes')

    # Waterfront
    data['waterfront_'] = data['waterfront'].apply(lambda x: 'sim' if x == '1'
    else 'não')

    # Colunas auxiliares pra def insights
    data['year'] = pd.to_datetime(data['date']).dt.year
    data['year'] = data['year'].astype(str)
    data['year_mouth'] = pd.to_datetime(data['date']).dt.strftime('%Y-%m')

    # Season
    data['mouth'] = pd.to_datetime(data['date']).dt.month
    data['season'] = data['mouth'].apply(lambda x: 'summer' if (x > 5) & (x < 8) else
    'spring' if (x > 2) & (x < 5) else
    'fall' if (x > 8) & (x < 12) else
    'winter')

    # Descrição das condições
    data['describe_condition'] = data['condition'].apply(lambda x: 'too bad' if x == 1 else
                                                         'bad' if x == 2 else
                                                         'median'if x == 3 else
                                                         'good' if x == 4 else
                                                         'excellent')

    return data

def buy_houses(data,geofile):

    st.sidebar.title('Projeto House Hocket')
    st.sidebar.subheader('https://github.com/feliperastelli')
    st.sidebar.write('     ')
    st.sidebar.write('Filtros para seleção dos imóveis sugeridos para compra e seus respectivos cenários de venda pós-compra')
    st.title('Imóveis sugeridos para compra')
    st.write('Condições: a) Imóveis abaixo do preço mediano da região - '
             'b) Imóveis em boas condições')

    # Agrupar os imóveis por região ( zipcode ).Encontrar a mediana do preço do imóvel.
    df1 = data[['zipcode', 'price']].groupby('zipcode').median().reset_index()
    df1 = df1.rename(columns={'price': 'price_median'})

    # Merge
    data = pd.merge(df1, data, on='zipcode', how='inner')

    # status
    for i in range(len(data)):
        if (data.loc[i, 'price'] < data.loc[i, 'price_median']) & (data.loc[i, 'condition'] >= 3):
            data.loc[i, 'status'] = 'buy'
        else:
            data.loc[i, 'status'] = 'no buy'

    # Seleção dos imóveis
    buy_houses = data[data['status'] == 'buy'].sort_values(by=['describe_condition', 'price'])

    f_condition = st.sidebar.multiselect('Enter Condition', buy_houses['describe_condition'].unique())
    f_zipcode = st.sidebar.multiselect('Enter Zipcode', buy_houses['zipcode'].unique())

    if (f_zipcode != []) & (f_condition != []):
        buy_houses = buy_houses.loc[(buy_houses['zipcode'].isin(f_zipcode)) & (buy_houses['describe_condition'].isin(f_condition)), :]
    elif (f_zipcode != []) & (f_condition == []):
        buy_houses = buy_houses.loc[data['zipcode'].isin(f_zipcode), :]
    elif (f_zipcode == []) & (f_condition != []):
        buy_houses = buy_houses.loc[buy_houses['describe_condition'].isin(f_condition), :]
    else:
        buy_houses = buy_houses.copy()

    st.dataframe(buy_houses[['id','zipcode', 'price', 'price_median', 'describe_condition']])
    st.sidebar.write('Foram encontrados {} imóveis dentro das condições acima, sugeridos para compra'.format(len(buy_houses)))

    st.title('Avaliação dos imóveis listados - Venda')
    st.write('Condição: a) Se o preço da compra for maior que a mediana da região + sazonalidade. O preço da venda será igual ao preço da compra + 10% ')
    st.write('Condição: b) Se o preço da compra for menor que a mediana da região + sazonalidade. O preço da venda será igual ao preço da compra + 30% ')

    # Agrupar os imóveis por região ( coluna zipcode ) e por sazonalidade(season)
    # Dentro de cada região/season encontrar a mediana do preço do imóvel.

    df2 = data[['zipcode', 'season', 'price']].groupby(['zipcode', 'season']).median().reset_index()
    df2 = df2.rename(columns={'price': 'price_median_season'})

    # unir df2 com df
    buy_houses = pd.merge(buy_houses, df2, how='inner', on=['zipcode', 'season'])

    for i in range(len(buy_houses)):
        if buy_houses.loc[i, 'price'] <= buy_houses.loc[i, 'price_median_season']:
            buy_houses.loc[i, 'sale_price'] = buy_houses.loc[i, 'price'] * 1.30
        elif buy_houses.loc[i, 'price'] > buy_houses.loc[i, 'price_median_season']:
            buy_houses.loc[i, 'sale_price'] = buy_houses.loc[i, 'price'] * 1.10
        else:
            pass

    buy_houses['profit'] = buy_houses['sale_price'] - buy_houses['price']
    st.dataframe(buy_houses[['id','zipcode', 'price','season', 'price_median_season', 'describe_condition', 'sale_price' , 'profit']])
    st.sidebar.write('O lucro total, dada as condições, será de US$ {} '.format(buy_houses['profit'].sum()))

    # Mapa de localização
    if st.checkbox('Mostrar mapas'):

        st.title('Visão geral dos imóveis selecionados')

        st.header('Localização')

        # Base Map - Folium
        density_map = folium.Map(location=[buy_houses['lat'].mean(), buy_houses['long'].mean()], default_zoom_start=15)
        marker_cluster = MarkerCluster().add_to(density_map)

        for name, row in buy_houses.iterrows():
            folium.Marker([row['lat'], row['long']],
                          popup='Buy price U${0} |Sell Price US$ {1} with profit of US$ {2}. Features: {3} sqft, {4} bedrooms, {5} bathrooms, year built: {6}'.format(
                              row['price'],
                              row['sale_price'],
                              row['profit'],
                              row['sqft_living'],
                              row['bedrooms'],
                              row['bathrooms'],
                              row['yr_built'])).add_to(marker_cluster)

        folium_static(density_map)

        # Mapa de densidade
        st.header('Densidade de lucro')
        df4 = buy_houses[['profit', 'zipcode']].groupby('zipcode').mean().reset_index()
        df4.columns = ['ZIP', 'PROFIT']
        geofile = geofile[geofile['ZIP'].isin(df4['ZIP'].tolist())]
        region_price_map = folium.Map(location=[buy_houses['lat'].mean(), buy_houses['long'].mean()], default_zoom_start=15)
        region_price_map.choropleth(data=df4,
                                    geo_data=geofile,
                                    columns=['ZIP', 'PROFIT'],
                                    key_on='feature.properties.ZIP',
                                    fill_color='YlOrRd',
                                    fill_opacity=0.7,
                                    line_opacity=0.2,
                                    legend_name='AVG PROFIT')

        folium_static(region_price_map)

    # ---- Insights - Imóveis selecionados --------- #

    st.title('Insights - Imóveis selecionados')
    df = buy_houses[['zipcode', 'bedrooms', 'bathrooms', 'floors', 'season',
                     'renovated', 'describe_condition', 'waterfront_', 'basement', 'grade', 'view', 'constrution']]

    st.subheader("Os atributos abaixo fornecem uma lucratividade maior dentre a seleção dos imóveis acima:")

    conditions = []
    for i in df.columns:
        ins = buy_houses[['profit', i]].groupby(i).sum().reset_index()

        plot = px.bar(ins, x=i, y='profit', color=i, labels={i:i,"profit": "Profit"},
                      template='simple_white')
        plot.update_layout(showlegend=False)
        st.plotly_chart(plot, use_container_width=True)
        ins2 = ins[ins['profit'] == ins['profit'].max()]
        conditions.append(ins2.iloc[0, 0])
        st.write('Imóveis mais lucrativos são os com "{}" igual a "{}"'.format(i, ins2.iloc[0, 0]))

    # Tabela com resumo
    st.subheader("Distribuição dos imóveis e lucros dentre os insights encontrados: ")
    dx = pd.DataFrame(columns=['atributo', 'condicao', 'total_imoveis', '%_imoveis', 'lucro_total', '%_lucro'])
    dx['atributo'] = ['zipcode', 'bedrooms', 'bathrooms', 'floors', 'season',
                      'renovated', 'describe_condition', 'waterfront_', 'basement', 'grade', 'view', 'constrution']
    dx['condicao'] = conditions

    for i in range(len(dx)):
        dx.loc[i, 'total_imoveis'] = buy_houses['id'][buy_houses[dx.loc[i, 'atributo']] == dx.loc[i, 'condicao']].count()
        dx.loc[i, '%_imoveis'] = float(dx.loc[i, 'total_imoveis'] / buy_houses['id'].count() * 100)
        dx.loc[i, 'lucro_total'] = buy_houses['profit'][buy_houses[dx.loc[i, 'atributo']] == dx.loc[i, 'condicao']].sum()
        dx.loc[i, '%_lucro'] = float(dx.loc[i, 'lucro_total'] / buy_houses['profit'].sum() * 100)

    dx["condicao"] = dx["condicao"].astype(str)
    st.dataframe(dx)

    return None

def insights(data):
    st.title('Outros insights de negócio')

    c1, c2 = st.beta_columns(2)

    #H1
    c1.subheader('Hipótese 1:  Imóveis com vista para a água são em média mais caros')
    h1 = data[['price', 'waterfront_']].groupby('waterfront_').mean().reset_index()
    fig2 = px.bar(h1, x='waterfront_', y='price', color='waterfront_', labels={"waterfront_": "Visão para água",
                                                                            "price": "Preço"}, template='simple_white')
    fig2.update_layout(showlegend=False)
    c1.plotly_chart(fig2, use_container_width=True)
    h1_percent = (h1.loc[1, 'price'] - h1.loc[0, 'price']) / h1.loc[0, 'price']
    c1.write('H1 é verdadeira, pois os imóveis com vista pra água são em média {0:.0%} mais caros'.format(h1_percent))

    # H2
    c2.subheader('Hipótese 2:  Imóveis com data de construção menor que 1955 são em média mais baratos')
    h2 = data[['price', 'constrution']].groupby('constrution').mean().reset_index()
    fig3 = px.bar(h2, x='constrution', y='price', color='constrution', labels={"constrution": "Ano da construção",
                                                                               "price": "Preço"},template='simple_white')
    fig3.update_layout(showlegend=False)
    c2.plotly_chart(fig3, use_container_width=True)
    h2_percent = (h2.loc[1, 'price'] - h2.loc[0, 'price']) / h2.loc[1, 'price']
    c2.write('H2 é falsa, pois os imóveis construídos antes de 1955, são em média apenas {0:.0%} mais baratos'.format(h2_percent))

    c3, c4 = st.beta_columns(2)

    #H3
    c3.subheader('Hipótese 3:  Imóveis sem porão são maiores do que imóveis com porão')
    h3 = data[['sqft_lot', 'basement']].groupby('basement').mean().reset_index()
    fig4 = px.bar(h3, x='basement', y='sqft_lot', color='basement', labels={"basement": "Imóvel com porão",
                                                                               "sqft_lot": "Tamanho total do imóvel"},
                  template='simple_white')
    fig4.update_layout(showlegend=False)
    c3.plotly_chart(fig4, use_container_width=True)
    h3_percent = (h3.loc[0,'sqft_lot'] - h3.loc[1,'sqft_lot']) / h3.loc[1,'sqft_lot']
    c3.write('H3 é verdadeira, pois os imóveis sem porão, possuem área do lote {0:.0%} maior'.format(h3_percent))

    #H4
    c4.subheader('Hipótese 4:  Houve crescimento do preço médio dos imóveis YoY ( Year over Year )')
    h4 = data[['price', 'year']].groupby('year').mean().reset_index()
    fig5 = px.bar(h4, x='year', y='price', color='year', labels={"year": "Ano", "price": "Preço médio"},
                  template='simple_white')
    fig5.update_layout(showlegend=False)
    c4.plotly_chart(fig5, use_container_width=True)
    h4_percent = (h4.loc[1, 'price'] - h4.loc[0, 'price']) / h4.loc[0, 'price']
    c4.write('H4 é falsa, pois o crescimento do preço entre os anos foi de {0:.2%}'.format(h4_percent))

    #H5
    st.subheader('Hipótese 5:  Imóveis com mais quartos são em média mais caros')
    h5 = data[['price', 'bedrooms']].groupby('bedrooms').mean().reset_index()
    fig6 = px.bar(h5, x='bedrooms', y='price', color='bedrooms', labels={"bedrooms": "Nº quartos", "price": "Preço médio"},
                  template='simple_white')
    fig6.update_layout(showlegend=False)
    st.plotly_chart(fig6, x='bedrooms', y='price', use_container_width=True)
    median = h5['bedrooms'].median()
    bed_above = h5['price'][h5['bedrooms'] > median].mean()
    bed_below = h5['price'][h5['bedrooms'] < median].mean()
    h5_percent = (bed_above - bed_below) / bed_below
    st.write('H5 é verdadeira, pois os imóveis com mais quartos(acima de 5), são {0:.0%} mais caros'.format(h5_percent))

    return None

if __name__ == '__main__':

    st.set_page_config(layout='wide')
# ------------------ DATA EXTRATION ----------------------------------#
    path = 'kc_house_data.csv'
    url = 'https://opendata.arcgis.com/datasets/83fc2e72903343aabff6de8cb445b81c_2.geojson'
    data = get_data(path)
    geofile = get_geofile( url )
# ------------------ DATA TRANSFORMATION ----------------------------------#
    data = clean_data(data)
    data = set_feature( data )
    buy_houses( data, geofile )
    insights(data)
