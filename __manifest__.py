# -*- coding: utf-8 -*-
{
    'name': 'Minsa -Consulta Datos',
    'version': '1.0.0',
    'author': '',
    'category': 'Localisation/America',
    'summary': 'Consulta de datos a Servicios',
    'description': """

# Configuración
Establecer los parametros de sistema mpi_api_host, mpi_api_token de MPI.

# Servicios Disponibles
=====================
- Consulta Reniec.
- Consulta Mpi.

# Dependencias python
=====================
mpi-client


    """,
    'website': '',
    'depends': [],
    'external_dependencies': {
        'python': ['mpi_client']
    },
    'data': [
        'ir.model.access.csv',
        'consultadatos_data.xml',
    ],
    'qweb': [],
    'demo': [],
    'test': [],
    'images': [],
    'installable': True,
    'auto_install': False,
    'application': False,
    "sequence": 1,
}
