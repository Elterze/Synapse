#!/usr/bin/env python3
# -*- coding: utf8 -*-

import os
import logging, logging.handlers
from flask import Flask, request, jsonify
import json

from workflows.common.common import getConf
from workflows.Ews2Case import connectEws
from workflows.qradartest import createQradarAlert, closingQradarOffense

app_dir = os.path.dirname(os.path.abspath(__file__))

#create logger
logger = logging.getLogger('workflows')
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    #log format as: 2013-03-08 11:37:31,411 : : WARNING :: Testing foo
    formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')
    #handler writes into, limited to 1Mo in append mode
    if not os.path.exists('logs'):
        #create logs directory if does no exist (typically at first start)
        os.makedirs('logs')
    pathLog = app_dir + '/logs/synapse.log'
    file_handler = logging.handlers.RotatingFileHandler(pathLog, 'a', 1000000, 1)
    #level debug
    file_handler.setLevel(logging.DEBUG)
    #using the format defined earlier
    file_handler.setFormatter(formatter)
    #Adding the file handler
    logger.addHandler(file_handler)

app = Flask(__name__)

@app.route('/ews2case',methods=['GET'])
def ews2case():
    workflowReport = connectEws()
    if workflowReport['success']:
        return jsonify(workflowReport), 200
    else:
        return jsonify(workflowReport), 500

@app.route('/qradaralert',methods=['GET'])
def qradaralert():
    workflowReport = createQradarAlert()
    if workflowReport['success']:
        return jsonify(workflowReport), 200
    else:
        return jsonify(workflowReport), 500

@app.route('/thehivewebhook',methods=['POST'])
def thehivewebhook():
    data = json.loads(request.data)
    #print(json.dumps(data, indent=4))

    #Parse data
    obj_type = data['objectType']
    status = data['details']['status']
    try:
        resol_status = data['details']['resolutionStatus']
        note_text = "Closing summary : " + data['details']['summary']
    except KeyError:
        resol_status = None
        note_text = "Alert ignored"
    tags = data['object']['tags']
    offense_id = None
    for tag in tags:
        if tag[:8] == "QRadarID":
            offense_id = tag[9:]

    #Closing QRadar offense after closing TheHive case or alert
    if resol_status != "Duplicated" and "src:QRadar" in tags and ((
        obj_type == "alert" and status == "Ignored") or (
            obj_type == "case" and status == "Resolved")):
            workflowReport = closingQradarOffense(offense_id, note_text, resol_status)
            if workflowReport['success']:
                return jsonify(workflowReport), 200
            else:
                return jsonify(workflowReport), 500            
                
    return jsonify({'thehivewebhook': 'ok'}), 200


@app.route('/version', methods=['GET'])
def getSynapseVersion():
    return jsonify({'version': '1.0'}), 200

if __name__ == '__main__':
    cfg = getConf()
    app.run(debug=cfg.getboolean('api', 'debug'),
        host=cfg.get('api', 'host'),
        port=cfg.get('api', 'port'),
        threaded=cfg.get('api', 'threaded')
    )
