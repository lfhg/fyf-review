#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

"""

import pandas
import re
import glob
import numpy


url_fyf = 'https://www.felicesyforrados.cl/resultados/'

#primera tabla de la pagina
fyf_completo = pandas.read_html(url_fyf, index_col=0, header=0, parse_dates=False)[0]

#fechas vienen con formato dd-mm-yyyy, la conversion a datetime debe ser implicita
fyf_completo.index = pandas.to_datetime(fyf_completo.index, dayfirst=True)



#borramos la primera fila (resultados) y damos vuelta las fechas (de pasado a futuro)
fyf_completo = fyf_completo[1:]
fyf_completo = fyf_completo[::-1]

#nos quedamos sólo con las columnas que nos importan
fyf = fyf_completo.loc[:,['Fecha término','Sugerencia FyF']]

fondos = ['A', 'B', 'C', 'D', 'E']

#separamos las sugerencias en pesos por fondo en columnas (ej. "50% C / 50% E" en 0.5 columna C y 0.5 columna E)
for f in fondos:
    #regex
    reg = re.compile(r'(\d+)% ' + f)
    fyf[f] = [float(0 if reg.search(fyf.loc[ei,'Sugerencia FyF']) == None else reg.search(fyf.loc[ei,'Sugerencia FyF']).group(1))/100 for ei in fyf.index]

#dejamos eleccion sólo en fondos A y E: arbitrario: b=0.75A, c=0.5A, d=0.25A
fyf['A'] = fyf['A'] + 0.75*fyf['B'] + 0.5*fyf['C'] + 0.25*fyf['D']
fyf['E'] = fyf['E'] + 0.75*fyf['D'] + 0.5*fyf['C'] + 0.25*fyf['B']

#fyf.plot(kind='area', y=['A', 'E'])

#variacion de ipsa, no utilizado
#url_ipsa = 'https://stooq.com/q/d/l/?s=^ipsa&d1=20110101&d2=20210223&i=d'

#ipsa_completo = pandas.read_csv(url_ipsa, index_col=0, parse_dates=True)

#variacion diaria del precio de cierre
#ipsa_completo['var'] = ipsa_completo['Close']/ipsa_completo['Close'].shift(1)


#ipsa_completo.plot(y='Close')


pattern = './acciones/*.csv'
archivos = glob.glob(pattern)


re_acc = re.compile(r'./acciones/(.+)\.csv')

datos_acciones = {}


#dias habiles de desfase para la transaccion despues del cambio de fyf. 
#Debe ser al menos 1, los avisos salen despues del cierre de la bolsa
fyf_delay = 3
fecha_inicio = '2019-01'
fecha_fin = '2020-12'
precio_compra = 'High' #precio de compra de la accion. (High, Low o Price=cierre). Escenario pesimista compra al peor precio (high), vende al peor precio (low)
precio_venta = 'Low' #idem precio de venta

for csv in archivos:
    file = pandas.read_csv(csv, index_col=0, parse_dates=True)
    title = re_acc.search(csv).group(1)
    
    #orden de fechas, antigua a nueva
    orden = -1 if file.iloc[0].name > file.iloc[1].name else 1
    
    #borra dias sin transacciones (generalmente 31 de diciembre)
    for i in file.index:
        if file.loc[i, 'Vol.'] == '-':
            file.drop(index=i, inplace=True)
                        
    datos_acciones[title] = file[::orden]
    #nombre_acciones.append(title)

#funcion para calculo de ganancia/perdida de dupla de acciones, utilizando una estrategia de compra y venta definida
def calc_estrategia(fecha_inicio, fecha_fin, accion_A, accion_E, estrategia_original, nombre_A, nombre_E, delay):
    resultado = pandas.DataFrame(index=accion_A.index)
    #borramos las fechas que no estan en ambas listas, generalmente valor de USD en dias de bolsa cerrados
    for i in resultado.index:
        if i not in accion_E.index:
            resultado.drop(index=i, inplace=True)
    resultado['num_acciones_A'] = 0
    resultado['num_acciones_E'] = 0
    resultado['fondo'] = 0
    #si la accion es la misma, la estrategia es comprar y mantener por todo el periodo
    estrategia = pandas.DataFrame(index=resultado.index)
    if nombre_A == nombre_E:
        estrategia['A'] = 1
        estrategia['E'] = 0
    #construimos matriz de estrategia, colocando las fechas y luego rellenando las vacías 
    else:
        estrategia['A'] = numpy.nan
        estrategia['E'] = numpy.nan
        for est_i in estrategia_original.index:
            estrategia.loc[est_i, 'A'] = estrategia_original.loc[est_i, 'A']
            estrategia.loc[est_i, 'E'] = estrategia_original.loc[est_i, 'E']
        estrategia['A'] = estrategia['A'].shift(delay)
        estrategia['E'] = estrategia['E'].shift(delay)
        estrategia.fillna(method='ffill', inplace=True)
        
    resultado = resultado[fecha_inicio:fecha_fin]
    estrategia = estrategia[fecha_inicio:fecha_fin]
    
    prev_i = 0
    base_A = 0
    base_E = 0
    for i in resultado.index:
        #primera fecha de simulacion: compramos 100$ repartidos segun sugerencia de fyf por el mayor precio del dia
        if prev_i == 0:
            resultado.loc[i, 'num_acciones_A'] = 100*estrategia.loc[i, 'A']/accion_A.loc[i, precio_compra]
            resultado.loc[i, 'num_acciones_E'] = 100*estrategia.loc[i, 'E']/accion_E.loc[i, precio_compra]
            base_A = float(accion_A.loc[i, 'Price'])
            base_E = float(accion_E.loc[i, 'Price'])
        #fecha de cambio de sugerencia de fondos, aumenta la proporcion de fondo A
        elif estrategia.loc[i, 'A'] > estrategia.loc[prev_i, 'A']:
            #cantidad de acciones con que queda E: calculo lo hacemos con cierre anterior, calculamos nuevo numero de acciones con que nos debemos quedar
            resultado.loc[i, 'num_acciones_E'] = resultado.loc[prev_i, 'fondo'] * estrategia.loc[i, 'E'] / accion_E.loc[i, precio_venta]
            #cantidad de acciones con que queda A: diferencia de acciones de E, vendidas al menor precio de hoy de E, compradas al mayor precio de hoy de A (peor caso)
            resultado.loc[i, 'num_acciones_A'] = resultado.loc[prev_i, 'num_acciones_A'] + (resultado.loc[prev_i, 'num_acciones_E'] - resultado.loc[i, 'num_acciones_E']) \
                * accion_E.loc[i, precio_venta] / accion_A.loc[i, precio_compra]
        #cambio de sugerencia, aumenta la proporcion del fondo E
        elif estrategia.loc[i, 'E'] > estrategia.loc[prev_i, 'E']:
            resultado.loc[i, 'num_acciones_A'] = resultado.loc[prev_i, 'fondo'] * estrategia.loc[i, 'A'] / accion_A.loc[i, precio_venta]
            resultado.loc[i, 'num_acciones_E'] = resultado.loc[prev_i, 'num_acciones_E'] + (resultado.loc[prev_i, 'num_acciones_A'] - resultado.loc[i, 'num_acciones_A']) \
                * accion_A.loc[i, precio_venta] / accion_E.loc[i, precio_compra]
        #dia sin cambio de sugerencia, mantenemos constante cantidad de acciones
        else:
            resultado.loc[i, 'num_acciones_A'] = resultado.loc[prev_i, 'num_acciones_A']
            resultado.loc[i, 'num_acciones_E'] = resultado.loc[prev_i, 'num_acciones_E']
        prev_i = i
        resultado.loc[i, 'fondo'] = resultado.loc[i, 'num_acciones_A']*accion_A.loc[i, 'Price'] + resultado.loc[i, 'num_acciones_E']*accion_E.loc[i, 'Price']
        resultado.loc[i, 'accion_A'] = accion_A.loc[i, 'Price'] / base_A * 100
        resultado.loc[i, 'accion_E'] = accion_E.loc[i, 'Price'] / base_E * 100
    return resultado


matriz_resultados = pandas.DataFrame(index = datos_acciones.keys())

for x in datos_acciones.keys():
    matriz_resultados[x] = 0
    for y in datos_acciones.keys():
        res = calc_estrategia(fecha_inicio = fecha_inicio, fecha_fin = fecha_fin, accion_A = datos_acciones[x], accion_E = datos_acciones[y], estrategia_original = fyf, 
                                 nombre_A = x, nombre_E = y, delay = fyf_delay)
        matriz_resultados[x].loc[y] = res['fondo'].iloc[-1]

print(matriz_resultados)
matriz_resultados.to_csv('./resultados_'+fecha_inicio+'_'+fecha_fin+'_'+str(fyf_delay)+'.csv')

test = calc_estrategia(fecha_inicio, fecha_fin, datos_acciones['CAP'], datos_acciones['SQM-B'], fyf,
                       'CAP', 'SQM-B', fyf_delay)

test.plot(y=['fondo', 'accion_A', 'accion_E'])
#datos_acciones['SQM-B'][fecha_inicio:fecha_fin].plot(y='Price')
