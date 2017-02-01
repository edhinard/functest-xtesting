#!/usr/bin/python
#
# Copyright (c) 2015 All rights reserved
# This program and the accompanying materials
# are made available under the terms of the Apache License, Version 2.0
# which accompanies this distribution, and is available at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
import ConfigParser
import os
import re
import shutil
import subprocess

import opnfv.utils.constants as releng_constants

from functest.utils.constants import CONST
import functest.utils.functest_logger as ft_logger
import functest.utils.functest_utils as ft_utils
import functest.utils.openstack_utils as os_utils


IMAGE_ID_ALT = None
FLAVOR_ID_ALT = None
REPO_PATH = CONST.dir_repo_functest
GLANCE_IMAGE_PATH = os.path.join(CONST.dir_functest_data,
                                 CONST.openstack_image_file_name)
TEMPEST_TEST_LIST_DIR = CONST.dir_tempest_cases
TEMPEST_RESULTS_DIR = os.path.join(CONST.dir_results,
                                   'tempest')
TEMPEST_CUSTOM = os.path.join(REPO_PATH, TEMPEST_TEST_LIST_DIR,
                              'test_list.txt')
TEMPEST_BLACKLIST = os.path.join(REPO_PATH, TEMPEST_TEST_LIST_DIR,
                                 'blacklist.txt')
TEMPEST_DEFCORE = os.path.join(REPO_PATH, TEMPEST_TEST_LIST_DIR,
                               'defcore_req.txt')
TEMPEST_RAW_LIST = os.path.join(TEMPEST_RESULTS_DIR, 'test_raw_list.txt')
TEMPEST_LIST = os.path.join(TEMPEST_RESULTS_DIR, 'test_list.txt')

CI_INSTALLER_TYPE = CONST.INSTALLER_TYPE
CI_INSTALLER_IP = CONST.INSTALLER_IP

""" logging configuration """
logger = ft_logger.Logger("Tempest").getLogger()


def get_verifier_id():
    """
    Returns verifer id for current Tempest
    """
    cmd = ("rally verify list-verifiers | awk '/" +
           CONST.tempest_deployment_name +
           "/ {print $2}'")
    p = subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    deployment_uuid = p.stdout.readline().rstrip()
    if deployment_uuid == "":
        logger.error("Tempest verifier not found.")
        raise Exception('Error with command:%s' % cmd)
    return deployment_uuid


def get_verifier_deployment_id():
    """
    Returns deployment id for active Rally deployment
    """
    cmd = ("rally deployment list | awk '/" +
           CONST.rally_deployment_name +
           "/ {print $2}'")
    p = subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    deployment_uuid = p.stdout.readline().rstrip()
    if deployment_uuid == "":
        logger.error("Rally deployment not found.")
        raise Exception('Error with command:%s' % cmd)
    return deployment_uuid


def get_verifier_repo_dir(verifier_id):
    """
    Returns installed verfier repo directory for Tempest
    """
    if not verifier_id:
        verifier_id = get_verifier_id()

    return os.path.join(CONST.dir_rally_inst,
                        'verification',
                        'verifier-{}'.format(verifier_id),
                        'repo')


def get_verifier_deployment_dir(verifier_id, deployment_id):
    """
    Returns Rally deployment directory for current verifier
    """
    if not verifier_id:
        verifier_id = get_verifier_id()

    if not deployment_id:
        deployment_id = get_verifier_deployment_id()

    return os.path.join(CONST.dir_rally_inst,
                        'verification',
                        'verifier-{}'.format(verifier_id),
                        'for-deployment-{}'.format(deployment_id))


def configure_tempest(deployment_dir, IMAGE_ID=None, FLAVOR_ID=None):
    """
    Add/update needed parameters into tempest.conf file generated by Rally
    """
    tempest_conf_file = os.path.join(deployment_dir, "tempest.conf")
    if os.path.isfile(tempest_conf_file):
        logger.debug("Verifier is already configured.")
        logger.debug("Reconfiguring the current verifier...")
        cmd = "rally verify configure-verifier --reconfigure"
    else:
        logger.info("Configuring the verifier...")
        cmd = "rally verify configure-verifier"
    ft_utils.execute_command(cmd)

    logger.debug("Looking for tempest.conf file...")
    if not os.path.isfile(tempest_conf_file):
        logger.error("Tempest configuration file %s NOT found."
                     % tempest_conf_file)
        return releng_constants.EXIT_RUN_ERROR

    logger.debug("Updating selected tempest.conf parameters...")
    config = ConfigParser.RawConfigParser()
    config.read(tempest_conf_file)
    config.set(
        'compute',
        'fixed_network_name',
        CONST.tempest_private_net_name)
    if CONST.tempest_use_custom_images:
        if IMAGE_ID is not None:
            config.set('compute', 'image_ref', IMAGE_ID)
        if IMAGE_ID_ALT is not None:
            config.set('compute', 'image_ref_alt', IMAGE_ID_ALT)
    if CONST.tempest_use_custom_flavors:
        if FLAVOR_ID is not None:
            config.set('compute', 'flavor_ref', FLAVOR_ID)
        if FLAVOR_ID_ALT is not None:
            config.set('compute', 'flavor_ref_alt', FLAVOR_ID_ALT)
    config.set('identity', 'tenant_name', CONST.tempest_identity_tenant_name)
    config.set('identity', 'username', CONST.tempest_identity_user_name)
    config.set('identity', 'password', CONST.tempest_identity_user_password)
    config.set(
        'validation', 'ssh_timeout', CONST.tempest_validation_ssh_timeout)
    config.set('object-storage', 'operator_role',
               CONST.tempest_object_storage_operator_role)

    if CONST.OS_ENDPOINT_TYPE is not None:
        services_list = ['compute',
                         'volume',
                         'image',
                         'network',
                         'data-processing',
                         'object-storage',
                         'orchestration']
        sections = config.sections()
        for service in services_list:
            if service not in sections:
                config.add_section(service)
            config.set(service, 'endpoint_type',
                       CONST.OS_ENDPOINT_TYPE)

    with open(tempest_conf_file, 'wb') as config_file:
        config.write(config_file)

    # Copy tempest.conf to /home/opnfv/functest/results/tempest/
    shutil.copyfile(tempest_conf_file,
                    os.path.join(TEMPEST_RESULTS_DIR, 'tempest.conf'))

    return releng_constants.EXIT_OK


def configure_tempest_multisite(deployment_dir):
    """
    Add/update needed parameters into tempest.conf file generated by Rally
    """
    logger.debug("configure the tempest")
    configure_tempest(deployment_dir)

    logger.debug("Finding tempest.conf file...")
    tempest_conf_old = os.path.join(deployment_dir, 'tempest.conf')
    if not os.path.isfile(tempest_conf_old):
        logger.error("Tempest configuration file %s NOT found."
                     % tempest_conf_old)
        return releng_constants.EXIT_RUN_ERROR

    # Copy tempest.conf to /home/opnfv/functest/results/tempest/
    cur_path = os.path.split(os.path.realpath(__file__))[0]
    tempest_conf_file = os.path.join(cur_path, 'tempest_multisite.conf')
    shutil.copyfile(tempest_conf_old, tempest_conf_file)

    logger.debug("Updating selected tempest.conf parameters...")
    config = ConfigParser.RawConfigParser()
    config.read(tempest_conf_file)

    config.set('service_available', 'kingbird', 'true')
    # cmd = ("openstack endpoint show kingbird | grep publicurl |"
    #       "awk '{print $4}' | awk -F '/' '{print $4}'")
    # kingbird_api_version = os.popen(cmd).read()
    kingbird_api_version = os_utils.get_endpoint(service_type='kingbird')

    if CI_INSTALLER_TYPE == 'fuel':
        # For MOS based setup, the service is accessible
        # via bind host
        kingbird_conf_path = "/etc/kingbird/kingbird.conf"
        installer_type = CI_INSTALLER_TYPE
        installer_ip = CI_INSTALLER_IP
        installer_username = CONST.__getattribute__(
            'multisite_{}_installer_username'.format(installer_type))
        installer_password = CONST.__getattribute__(
            'multisite_{}_installer_password'.format(installer_type))

        ssh_options = ("-o UserKnownHostsFile=/dev/null -o "
                       "StrictHostKeyChecking=no")

        # Get the controller IP from the fuel node
        cmd = 'sshpass -p %s ssh 2>/dev/null %s %s@%s \
                \'fuel node --env 1| grep controller | grep "True\|  1" \
                | awk -F\| "{print \$5}"\'' % (installer_password,
                                               ssh_options,
                                               installer_username,
                                               installer_ip)
        multisite_controller_ip = "".join(os.popen(cmd).read().split())

        # Login to controller and get bind host details
        cmd = 'sshpass -p %s ssh 2>/dev/null  %s %s@%s "ssh %s \\" \
            grep -e "^bind_" %s  \\""' % (installer_password,
                                          ssh_options,
                                          installer_username,
                                          installer_ip,
                                          multisite_controller_ip,
                                          kingbird_conf_path)
        bind_details = os.popen(cmd).read()
        bind_details = "".join(bind_details.split())
        # Extract port number from the bind details
        bind_port = re.findall(r"\D(\d{4})", bind_details)[0]
        # Extract ip address from the bind details
        bind_host = re.findall(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
                               bind_details)[0]
        kingbird_endpoint_url = "http://%s:%s/" % (bind_host, bind_port)
    else:
        # cmd = "openstack endpoint show kingbird | grep publicurl |\
        #       awk '{print $4}' | awk -F '/' '{print $3}'"
        # kingbird_endpoint_url = os.popen(cmd).read()
        kingbird_endpoint_url = os_utils.get_endpoint(service_type='kingbird')

    try:
        config.add_section("kingbird")
    except Exception:
        logger.info('kingbird section exist')
    config.set('kingbird', 'endpoint_type', 'publicURL')
    config.set('kingbird', 'TIME_TO_SYNC', '20')
    config.set('kingbird', 'endpoint_url', kingbird_endpoint_url)
    config.set('kingbird', 'api_version', kingbird_api_version)
    with open(tempest_conf_file, 'wb') as config_file:
        config.write(config_file)

    return releng_constants.EXIT_OK
