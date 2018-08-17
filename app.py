#!/usr/bin/env python3
# -*- coding: utf8 -*-

import os
import logging, logging.handlers
from flask import Flask, request, jsonify
from celery import Celery
from celery.task.control import inspect
import json
import time

from workflows.common.common import getConf
from workflows.Ews2Case import connectEws
from workflows.qradartest import createQradarAlert, closingQradarOffense

app_dir = os.path.dirname(os.path.abspath(__file__))

#get configuration from configuration file
cfg = getConf()

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

#create Flask app
app = Flask(__name__)

#create Celery worker
celery = Celery(app.name, broker=cfg.get('Celery', 'broker'), backend=cfg.get('Celery', 'backend'))
celery.conf.update(app.config)

@celery.task(bind=True, name="QradarPeriodic")
def qradarperiodictask(self, interval):
    """Start a Celery worker launching createQradarAlert every interval seconds"""
    def is_revoked():
        i = celery.control.inspect()
        revoked_tasks = list(i.revoked().values())[0]
        for task in revoked_tasks :
            if task == self.request.id :
                return True
            else :
                return False

    self.update_state(state='RUNNING')
    while not is_revoked() :
        print("Fetching QRadar offenses...")
        createQradarAlert()
        print("Completed!")
        time.sleep(interval)
    return {'status': 'Task completed!'}

#create Flask endpoints
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

@app.route('/launchqradartask', methods=['GET'])
def launch_task():
    task = qradarperiodictask.apply_async((30,))
    if task.state == "RUNNING" or task.state == "PENDING":
        return jsonify({'sucess': True}), 200
    else:
        return jsonify({'sucess': False}), 500

@app.route('/revokeqradartask', methods=['GET'])
def revoke():
    report = dict()
    report['success'] = False
    i = celery.control.inspect()
    running_tasks = list(i.active().values())[0]
    for task in running_tasks:
        if task['name'] == "QradarPeriodic":
            worker = qradarperiodictask.AsyncResult(task['id'])
            worker.revoke(wait=True, timeout=5)
            print(task['name'] + " worker with id  " + task['id'] +
            " has been revoked")
            report['success'] = True
    if report['success']:
        return jsonify(report), 200
    else:
        return jsonify(report), 500

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
    app.run(debug=cfg.getboolean('api', 'debug'),
        host=cfg.get('api', 'host'),
        port=cfg.get('api', 'port'),
        threaded=cfg.get('api', 'threaded')
    )