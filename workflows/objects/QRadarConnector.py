#!/usr/bin/env python3
# -*- coding: utf8 -*-

import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import logging
import json
from QRadarApi import QRadarApi

class QRadarConnector:
    'QRadar connector'

    def __init__(self, cfg):
        self.logger = logging.getLogger('workflows.' + __name__)
        self.cfg = cfg

        self.qradarApi = self.connect()

    def connect(self):
        self.logger.info('%s.connect starts', __name__)

        server = self.cfg.get('QRadar', 'server')
        certificate_file = self.cfg.get('QRadar', 'certificate_file')
        version = self.cfg.get('QRadar', 'version')
        if 'auth_token' in self.cfg['QRadar']:
            auth_token = self.cfg.get('QRadar', 'auth_token')
            return QRadarApi(server, certificate_file, version, auth_token=auth_token)
        elif ('username' in self.cfg['QRadar']) and ('password' in self.cfg['QRadar']):
            username = self.cfg.get('QRadar', 'username')
            password = self.cfg.get('QRadar', 'password')
            return QRadarApi(server, certificate_file, version, username=username, password=password)
        else:
            raise Exception('No valid credentials found in configuration.')

    def getOffenses(self):
        self.logger.info('%s.getOffenses starts', __name__)

        #Only retrieve opened offenses
        response = self.qradarApi.call_api('/siem/offenses', 'GET', params={'status':'OPEN'})
        return json.loads(response.read().decode('utf-8'))

    def addNote(self, offense_id, note_text):
        self.logger.info('%s.addNote starts', __name__)

        params = {'note_text': note_text}
        #Send the note to the QRadar offense
        response = self.qradarApi.call_api('siem/offenses/' + offense_id + '/notes','POST', params=params)
        return response

    def closeOffense(self, offense_id, closing_reason_id):
        self.logger.info('%s.getOffenses starts', __name__)

        #Close the QRadar offense
        response = self.qradarApi.call_api(
            'siem/offenses/' + offense_id + '?status=CLOSED&closing_reason_id=' +
            closing_reason_id + '&fields=id,description,status,offense_type,offense_source',
             'POST')
        return response