#!/usr/bin/env python3
# -*- coding: utf8 -*-

import os, sys
import logging
current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = current_dir + '/..'
sys.path.insert(0, current_dir)

import json, datetime
from collections import defaultdict
from common.common import getConf
from objects.QRadarConnector import QRadarConnector
from objects.TheHiveConnector import TheHiveConnector
from thehive4py.models import Case, CaseTask, CaseTaskLog, CaseObservable, AlertArtifact, Alert
from thehive4py.query import *

def createQradarAlert():
    logger = logging.getLogger(__name__)
    logger.info('%s.createQradarAlert starts', __name__)

    report = dict()
    report['success'] = bool()
    
    try:

        cfg = getConf()
        qradarConnector = QRadarConnector(cfg)
        theHiveConnector = TheHiveConnector(cfg)

        #Retrieve QRadar offenses with "OPEN" status
        response = qradarConnector.getOffenses()
        
        for offense in response:
            #Check if offense is already imported in TheHive
            theHive_alert = theHiveConnector.getAlerts({'sourceRef': 'QR' + str(offense['id'])}).json()
            if theHive_alert == []:
                print('QR' + str(offense['id']) + ' not imported')

                #Import opened offense in TheHive

                ##Create a list of AlertArtifact objects
                artifact_fields = {
                    'source_network': ('domain', 'STRING'),
                    'destination_networks': ('domain', 'STRING_LIST'),
                    'offense_source': ('ip', 'STRING')}
                artifacts_dict = defaultdict(list)
                for field in artifact_fields:
                    if artifact_fields[field][1] == 'STRING_LIST':
                        for elmt in offense[field]:
                            artifacts_dict[artifact_fields[field][0]].append(elmt)
                    elif artifact_fields[field][1] == 'STRING':
                        artifacts_dict[artifact_fields[field][0]].append(offense[field])
                artifacts_list = theHiveConnector.craftAlertArtifact(artifacts_dict)
                print(artifacts_dict)
                print(artifacts_list)

                ##Prepare other fields for an alert
                title = "#" + str(offense['id']) + " QRadar - " + offense['description']
                description = ' / '.join(offense['categories'])
                if offense['severity'] < 3:
                    severity = 1
                elif offense['severity'] > 6:
                    severity = 3
                else:
                    severity = 2
                date = offense['start_time']
                tags=['Synapse', 'src:QRadar', 'QRadarID:' + str(offense['id'])]
                sourceRef = 'QR' + str(offense['id'])

                ##Create Alert object and send it to TheHive
                alert = theHiveConnector.craftAlert(title, description, severity, date,
                    tags, sourceRef, artifacts_list)
                theHiveConnector.createAlert(alert)

            else :
                print('QR' + str(offense['id']) + ' already imported')

        report['success'] = True
        return report

    except Exception as e:
        logger.error('Failed to create alert from QRadar offense', exc_info=True)
        report['success'] = False
        return report

def closingQradarOffense(offense_id, note_text, resol_status):
    logger = logging.getLogger(__name__)
    logger.info('%s.closingQradarOffense starts', __name__)

    report = dict()
    report['success'] = bool()

    try:
        cfg = getConf()
        qradarConnector = QRadarConnector(cfg)

        #Add closing summary as a note to the offense
        response_note = qradarConnector.addNote(offense_id, note_text)

        #Determine closing reason
        if resol_status is None or resol_status == "Indeterminate":
            closing_reason_id = '1' #Non-Issue
        elif resol_status == "FalsePositive":
            closing_reason_id = '2' #False Positive
        else:
            closing_reason_id = '3' #Policy Violation

        response_closing = qradarConnector.closeOffense(offense_id, closing_reason_id)

        report['success'] = True
        return report

    except Exception as e:
        logger.error('Failed to close QRadar offense', exc_info=True)
        report['success'] = False
        return report


#print(len(parsed_response))
#print(json.dumps(parsed_response, indent=4))

#Check id of the last QRadar offense in TheHive
#th_last_offense = theHiveConnector.getAlerts({"tags": "src:Test"}, range='0-1', sort=['-date']).json()
#if th_last_offense == []:
#    th_last_offense_id = 
#th_last_offense_id = int(th_last_offense[0]['sourceRef'][4:-1])
#print(th_last_offense_id)
#result = theHiveConnector.getAlerts(String("^QR*")).json()
#print(result)

#for elmt in result:
#    print(elmt['sourceRef']  + " : " + str(datetime.datetime.fromtimestamp(elmt['lastSyncDate'] / 1e3).strftime('%Y-%m-%d %H:%M:%S')))

#QRadar query
#response = qradarConnector.qradarApi.call_api('/siem/offenses', 'GET', params={'filter':'id>63'}, headers={'Range':'items=0-1'})
#parsed_response = json.loads(response.read().decode('utf-8'))
#print(type(parsed_response))
#print(json.dumps(parsed_response, indent=4))

#TheHive query
#result = theHiveConnector.getAlerts({"tags": "src:CIRCL"}, range='0-1').json()
#print(str(len(result)))

