"""
utils

Created by: Martin Sicho
On: 17.05.22, 9:55
"""
import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import warnings

from drugex.logs import config, logger, setLogger
from drugex.logs.config import LogFileConfig

BACKUP_DIR_FOLDER_PREFIX = 'backup'

def export_conda_environment(filepath: str):
    """Export the conda environment to a yaml file.

    Args:
        filepath (str): path to the yaml file

    Raises:
        subprocess.CalledProcessError: if the command fails
        Exception: if an unexpected error occurs
    """
    try:
        cmd = f"conda env export > {filepath}"
        subprocess.run(cmd, shell=True, check=True)
        print(f"Environment exported to {filepath} successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error exporting the environment: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def enable_file_logger(log_folder, filename, debug=False, log_name=None, git_hash=None, init_data=None, disable_existing_loggers=True):
    
    path = os.path.join(log_folder, filename)
    config.config_logger(path, debug, disable_existing_loggers=disable_existing_loggers)

    # get logger and init configuration
    log = logging.getLogger(filename) if not log_name else logging.getLogger(log_name)
    log.setLevel(logging.INFO if not debug else logging.DEBUG)
    setLogger(log)
    settings = LogFileConfig(path, log, debug)

    # Begin log file
    config.init_logfile(log, json.dumps(init_data, sort_keys=False, indent=2))
    
    if not debug:
        # Disable 'qsprpred' logger if it exists
        # This is a hack to prevent the 'qsprpred' logger from writing to the log file
        # but this should be already disabled by the 'disable_existing_loggers' flag
        # and other loggers dont seem to cause this problem
        loggers = logging.Logger.manager.loggerDict.keys()
        if 'qsprpred' in loggers:
            logging.getLogger('qsprpred').disable = True

    return settings

def generate_backup_runID(path='.'):

    """ 
    Generates runID for generation backups of files to be overwritten 
    If no previous backfiles (starting with #) exists, runid is set to 0, else to previous runid+1
    """

    regex = f'{BACKUP_DIR_FOLDER_PREFIX}_[0-9]+'
    previous = [ int(re.search('[0-9]+', file)[0]) for file in os.listdir(path) if re.match(regex, file)]

    runid = 1
    if previous:
        runid = max(previous) + 1

    # backup_files = sorted([ file for file in os.listdir(path) if file.startswith('#')])
    # if len(backup_files) == 0 :
    #     runid = 0
    # else :
    #     previous_id = max([int(file.split('.')[-1][:-1]) for file in backup_files])
    #     runid = previous_id + 1

    return runid

def generateBackupDir(root, backup_id):
    new_dir = os.path.join(root, f'{BACKUP_DIR_FOLDER_PREFIX}_{str(backup_id).zfill(5)}')
    if not os.path.exists(new_dir):
        os.makedirs(new_dir)
    return new_dir

def backUpFilesInFolder(_dir, backup_id, output_prefixes, output_extensions='dummy', cp_suffix=None):
    message = ''
    existing_files = os.listdir(_dir)
    if cp_suffix and all([file.split('.')[0].endswith(cp_suffix) for file in existing_files]):
        return message
    for file in existing_files:
        if file.startswith(output_prefixes) or file.endswith(output_extensions):
            backup_dir = generateBackupDir(_dir, backup_id)
            backup_log = open(os.path.join(backup_dir, 'backuplog.log'), 'w')
            backup_log.write(f'[{datetime.datetime.now()}] : {file} was moved from {os.path.abspath(_dir)}' )
            message += f"Already existing '{file}' was copied to {os.path.abspath(backup_dir)}\n"
            if cp_suffix != None and file.split('.')[0].endswith(cp_suffix):
                shutil.copyfile(os.path.join(_dir, file), os.path.join(backup_dir, file))
            else:
                os.rename(os.path.join(_dir, file), os.path.join(backup_dir, file))
    return message


def backUpFiles(base_dir : str, folder : str, output_prefixes : tuple, cp_suffix=None):

    dir = base_dir + '/' + folder 
    if os.path.exists(dir):
        backup_id = generate_backup_runID(dir)    
        if folder in 'data':
            message = backUpFilesInFolder(dir, backup_id, output_prefixes, output_extensions=('json', 'log'))
        elif folder == 'envs':
            message = backUpFilesInFolder(dir, backup_id, output_prefixes, output_extensions=('json', 'log'), cp_suffix=cp_suffix )
        elif folder == 'generators':
            message = backUpFilesInFolder(dir, backup_id, output_prefixes)
        elif folder == 'new_molecules':
            message = backUpFilesInFolder(dir, backup_id, output_prefixes, output_extensions=('json', 'log'))
        return message
    else:
        return ''

def callwarning(warning_text, exp=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if exp:
                warnings.warn(warning_text, exp, stacklevel=2)
            else:
                logger.warning(warning_text)
            return func(*args, **kwargs)
        return wrapper
    return decorator