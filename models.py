# -*- coding: utf-8 -*-

import datetime as dt
import logging
from dateutil.relativedelta import relativedelta
from PIL import ImageFile

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from mpi_client import client as mpiclient

ImageFile.LOAD_TRUNCATED_IMAGES = True

datetime = dt.datetime
timedelta = dt.timedelta

TIPODOC_NO_SE_CONOCE = '00'
TIPODOC_DNI = '01'
TIPODOC_LIBRETA_MILITAR = '02'
TIPODOC_CARNET_EXTRANJERIA = '03'
TIPODOC_ACTA_NACIMIENTO = '04'
TIPODOC_PASAPORTE = '06'
TIPODOC_DNI_EXTRANJERO = '07'

_logger = logging.getLogger(__name__)


class ConsultadatosReniec(models.AbstractModel):
    _description = "Consulta de datos Reniec"
    _name = 'consultadatos.reniec'

    @api.model
    def consultardni(self, numerodni):
        return self.env['consultadatos.mpi'].consultardni(numerodni)


class ConsultadatosMpi(models.Model):
    _description = "Consulta de datos de Mpi"
    _name = 'consultadatos.mpi'

    tipo_consulta = fields.Selection([('ciudadano', 'Ciudadano'), ('sis', 'Sis')], index=True)
    tipo_documento = fields.Char('Tipo de Documento', size=3, required=True, index=True)
    identificacion = fields.Char('Número documento/uuid', required=True, index=True)
    text_json = fields.Text('Contenido')
    fecha_mpi = fields.Datetime('Actualización MPI', required=True)
    status = fields.Char('Status', default='200', size=3)

    _sql_constraints = [
        ('documento_unique', 'unique(tipo_consulta, tipo_documento, identificacion)',
         'El documento debe ser único!'),
    ]

    def get_parametros_mpi(self):
        """
        Devuelve los parametros host y token de MPI contenidos en ir.config_parameter
        returna (mpiclient, mpi_api_host, mpi_api_token)
        """
        get_param = self.env['ir.config_parameter'].sudo().get_param

        modo_online = get_param('consultadatos.modo_online') or \
            get_param('modo_online') or 'True'

        if modo_online.title() not in ['True', '1']:
            return {}

        mpi_api_host = get_param('mpi_api_host') or \
            get_param('consultadatos.mpi_api_host') or False
        mpi_api_token = get_param('mpi_api_token') or \
            get_param('consultadatos.mpi_api_token') or False

        if not mpi_api_host or mpi_api_host and mpi_api_host == 'mpi_api_host':
            raise ValidationError('No esta configurado el parámetro de sistema mpi_api_host')
        elif not mpi_api_token or mpi_api_token and mpi_api_token == 'mpi_api_host':
            raise ValidationError('No esta configurado el parámetro de sistema mpi_api_token')

        mpiclient.MPI_API_HOST = mpi_api_host

        return (mpiclient, mpi_api_host, mpi_api_token)

    @api.model
    def consultardocumento(self, numero_documento, tipo_documento):
        if not numero_documento:
            raise ValidationError('No se especificó el número de documento')

        if not tipo_documento:
            raise ValidationError('No se especificó el tipo de documento')

        dict_estado_civil = {
            '1': 'single',  # soltero(a)
            '2': 'married',  # casado(a)
            '3': 'widower',  # viudo(a)
            '4': 'divorced',  # divorciado(a)
        }
        dict_sexo = {
            '1': 'male',
            '2': 'female',
        }

        data = self.ver(numero_documento, tipo_documento=tipo_documento)

        if data.get('error'):
            raise ValidationError('Error: {} | Message: {}'.format(data.get('error'), data.get('message')))

        res = dict(
            dni=data['numero_documento'],
            ape_paterno=data['apellido_paterno'],
            ape_materno=data['apellido_materno'],
            nombres=data['nombres'],

            # Datos Nacimiento
            nacimiento=dict(
                ubigeo=data['nacimiento_ubigeo'],
                fecha=data['fecha_nacimiento'],
            ),

            # Datos Domicilio
            domicilio=dict(
                direccion=data['domicilio_direccion'],
                ubigeo=data.get('get_distrito_domicilio_ubigeo_reniec', False),
                direccion_descripcion=data['domicilio_direccion'],
            ),

            sexo=dict_sexo[data['sexo']],
            estadocivil=dict_estado_civil[data['estado_civil']],

            fotografia=data['foto'],
            telefono=data['telefono'],
            celular=data['celular'],
        )
        return res

    @api.model
    def consultardni(self, numerodni):
        message = False
        if not numerodni:
            message = u'No se especificó el número de dni'

        if len(numerodni) != 8 or not numerodni.isdigit():
            message = u'Error en el dni, debe ser de 8 digitos'

        if message:
            raise ValidationError(message)

        return self.consultardocumento(numerodni, TIPODOC_DNI)

    def ver(self, numero_documento_or_uuid, tipo_documento="01", tipo_consulta='ciudadano', minutos_sinactualizar=None):
        if not numero_documento_or_uuid:
            logging.debug('No se especifico el numero documento')
            return {}

        self = self.sudo()

        domain = [('tipo_consulta', '=', tipo_consulta),
                  ('tipo_documento', '=', tipo_documento),
                  ('identificacion', '=', numero_documento_or_uuid)]
        record = self.search(domain, limit=1)

        if not record:
            res_json = self.__ver(numero_documento_or_uuid, tipo_documento=tipo_documento, tipo_consulta=tipo_consulta)
            status = 'errors' in res_json and res_json.get('errors')\
                and len(res_json['errors']) and res_json['errors'][0].get('status') or '200'

            if status == '404':
                return {'error': '404', 'message': 'Documento no encontrado'}

            if not res_json:
                return {}

            values = dict(tipo_consulta=tipo_consulta,
                          tipo_documento=tipo_documento,
                          identificacion=numero_documento_or_uuid,
                          text_json=str(res_json),
                          fecha_mpi=fields.Datetime.now(),
                          status=status)

            record = self.create(values)
        return eval(record.text_json)

    def __ver(self, numero_documento_or_uuid, tipo_documento="01", tipo_consulta='ciudadano'):
        if tipo_documento in ('dni', '1', '01'):
            tipo_documento = TIPODOC_DNI
        elif tipo_documento in ('ce', '3', '03'):
            tipo_documento = TIPODOC_CARNET_EXTRANJERIA
        elif tipo_documento not in (
                TIPODOC_NO_SE_CONOCE, TIPODOC_LIBRETA_MILITAR,
                TIPODOC_ACTA_NACIMIENTO, TIPODOC_PASAPORTE, TIPODOC_DNI_EXTRANJERO):
            raise ValidationError(u'Tipo de documento no válido')

        if not numero_documento_or_uuid:
            return {}
        parametros_mpi = self.get_parametros_mpi()
        if not parametros_mpi:
            return {}

        mpiclient, mpi_api_host, mpi_api_token = parametros_mpi
        # Verificando si no hay conexión al webservice
        res = {}
        try:
            mpi_client = mpiclient.CiudadanoClient(mpi_api_token)
            if tipo_consulta == 'ciudadano':
                response = mpi_client.ver(numero_documento_or_uuid, tipo_documento)
            elif tipo_consulta == 'sis':
                response = mpi_client.ver_datos_sis(numero_documento_or_uuid, tipo_documento)
            else:
                raise ValidationError('__ver tipo_consulta {} no es válido'.format(tipo_consulta))
            res.update(response)
        except Exception as e:
            _logger.error(e.message)
            res['message'] = e.message
            res['error'] = "Connection error MPI."
        return res

    def ver_datos_sis(self, numero_documento_or_uuid, tipo_documento="01"):
        ciudano = self.ver(numero_documento_or_uuid, tipo_documento)
        if ciudano and ciudano.get('tipo_seguro', False) and ciudano.get('tipo_seguro') == '2':
            return self.ver(numero_documento_or_uuid, tipo_documento, tipo_consulta='sis')
        else:
            return {}

    @api.model
    def _cron_delete(self):
        get_param = self.env['ir.config_parameter'].sudo().get_param
        minutos_sinactualizar = get_param('mpi_minutos_sinactualizar') or 1
        try:
            minutos_sinactualizar = int(minutos_sinactualizar)
        except Exception:
            minutos_sinactualizar = 0
        now = fields.Datetime.from_string(fields.Datetime.now())
        time1 = now - relativedelta(minutes=minutos_sinactualizar)
        time2 = now - relativedelta(minutes=1)

        domain = ['|',
                  '&',
                  ('status', '=', '200'),
                  ('fecha_mpi', '<=', fields.Datetime.to_string(time1)),
                  '&',
                  ('status', '!=', '200'),
                  ('fecha_mpi', '<=', fields.Datetime.to_string(time2))]
        self.search(domain).unlink()
