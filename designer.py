#!/usr/bin/env python
import os
import json
import torch
import argparse
import pandas as pd

from rdkit import rdBase
from torch.utils.data import DataLoader

import math

import drugex.logs.utils
import utils
from train import SetGeneratorAlgorithm, CreateDesirabilityFunction

import logging
import logging.config
from datetime import datetime


rdBase.DisableLog('rdApp.error')
torch.set_num_threads(1)

def DesignArgParser(txt=None):
    """ Define and read command line arguments """
    
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument('-b', '--base_dir', type=str, default='.',
                        help="Base directory which contains folders 'data' and 'output'")
    parser.add_argument('-k', '--keep_runid', action='store_true', help="If included, continue from last run")
    parser.add_argument('-p', '--pick_runid', type=int, default=None, help="Used to specify a specific run id")
    parser.add_argument('-d', '--debug', action='store_true')

    parser.add_argument('-g', '--generator', type=str, default='ligand_mf_brics_gpt_128',
                        help="Name of final generator model file without .pkg extension")
    parser.add_argument('-i', '--input', type=str, default='ligand_4:4_brics_test',
                        help="For v3, name of file containing fragments for generation without _graph.txt / _smi.txt extension") 
    parser.add_argument('-n', '--num', type=int, default=1,
                        help="For v2 number of molecules to generate in total, for v3 number of molecules to generate per fragment")
    parser.add_argument('-gpu', '--gpu', type=str, default='1,2,3,4',
                        help="List of GPUs") 
    parser.add_argument('-bs', '--batch_size', type=int, default=1048,
                        help="Batch size")
    parser.add_argument('-ng', '--no_git', action='store_true',
                        help="If on, git hash is not retrieved")    
    if txt:
        args = parser.parse_args(txt)
    else:
        args = parser.parse_args()
        
    # Load parameters generator/environment from trained model
    with open(args.base_dir + '/generators/' + args.generator + '.json') as f:
        g_params = json.load(f)
    
    args.algorithm = g_params['algorithm']
    args.epsilon = g_params['epsilon']
    args.beta = g_params['beta']
    args.scheme = g_params['scheme']
    args.env_alg = g_params['env_alg']
    args.env_task = g_params['env_task']
    args.active_targets = g_params['active_targets']
    args.inactive_targets = g_params['inactive_targets']
    args.activity_threshold = g_params['activity_threshold']
    args.qed = g_params['qed']
    args.ra_score = g_params['ra_score']
    args.ra_score_model = g_params['ra_score_model']
    args.env_runid = g_params['env_runid']
    args.data_runid = g_params['data_runid']
    args.molecular_weight = g_params['molecular_weight']
    args.mw_thresholds = g_params['mw_thresholds']
    args.logP = g_params['logP']
    args.logP_thresholds = g_params['logP_thresholds']
    
    args.targets = args.active_targets + args.inactive_targets

    if args.no_git is False:
        args.git_commit = drugex.logs.utils.commit_hash(os.path.dirname(os.path.realpath(__file__)))
    print(json.dumps(vars(args), sort_keys=False, indent=2))
    return args

def Design(args):
    
    # Get run id
    runid = utils.get_runid(log_folder=os.path.join(args.base_dir,'logs'),
                            old=args.keep_runid,
                            id=args.pick_runid)

    # Default input file prefix in case of pretraining and finetuning
    if args.data_runid is None:
        args.data_runid = runid  
        
    if args.env_runid is None:
        args.env_runid = runid

    # Configure logger
    utils.config_logger('%s/logs/%s/train.log' % (args.base_dir, runid), args.debug)

    # Get logger, include this in every module
    log = logging.getLogger(__name__)
    
    utils.devices = eval(args.gpu) if ',' in args.gpu else [eval(args.gpu)]
    torch.cuda.set_device(utils.devices[0])
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu
    
    if not os.path.exists(args.base_dir + '/new_molecules'):
        os.makedirs(args.base_dir + '/new_molecules')
    
    # Initialize voc
    if args.algorithm == 'graph':
        try: 
            voc = utils.VocGraph( args.base_dir + '/data/voc_graph_%s.txt' % runid, max_len=80, n_frags=4)
        except:
            log.warning('Reading voc_graph.txt instead of voc_graph_%s.txt' % runid)
            voc = utils.VocGraph( args.base_dir + '/data/voc_graph.txt', max_len=80, n_frags=4)
    else:
        try:
            path = args.base_dir + '/data/voc_smiles_%s.txt' % runid
            if args.algorithm == 'gpt':
                voc = utils.Voc(path, src_len=100, trg_len=100)
            else:
                voc = utils.VocSmiles(path, max_len=100)
        except:
            log.warning('Reading voc_smiles.txt instead of voc_smiles_%s.txt' % runid)
            path = args.base_dir + '/data/voc_smiles.txt' 
            if args.algorithm == 'gpt':
                voc = utils.Voc( path, src_len=100, trg_len=100)
            else:
                voc = utils.VocSmiles( path, max_len=100)
    
    # Load data (only done for encoder-decoder models)
    if args.algorithm == 'graph':
        data = pd.read_table(args.base_dir + '/data/' + args.input + '_graph.txt')
        data = torch.from_numpy(data.values).long().view(len(data), voc.max_len, -1)
        loader = DataLoader(data, batch_size=args.batch_size)  
    elif args.algorithm != 'rnn':
        data = pd.read_table(args.base_dir + '/data/' + args.input + '_smi.txt')
        data = voc.encode([seq.split(' ')[:-1] for seq in data.values])
        loader = DataLoader(data, batch_size=args.batch_size)
    
    # Load generator model
    gen_path = args.base_dir + '/generators/' + args.generator + '.pkg'
    agent = SetGeneratorAlgorithm(voc, args.algorithm)
    agent.load_state_dict(torch.load( gen_path, map_location=utils.dev))
    # Set up environment-predictor
    objs, keys, mods, ths = CreateDesirabilityFunction(args.base_dir, 
                                                       args.env_alg, 
                                                       args.env_task, 
                                                       args.scheme, 
                                                       args.env_runid,
                                                       active_targets=args.active_targets,
                                                       inactive_targets=args.inactive_targets,
                                                       activity_threshold=args.activity_threshold, 
                                                       qed=args.qed, 
                                                       ra_score=args.ra_score, 
                                                       ra_score_model=args.ra_score_model,
                                                       mw=args.molecular_weight,
                                                       mw_ths=args.mw_thresholds,
                                                       logP=args.logP,
                                                       logP_ths=args.logP_thresholds,
                                                      )
    env =  utils.Env(objs=objs, mods=None, keys=keys, ths=ths)
    
    out = args.base_dir + '/new_molecules/' + args.generator + '.tsv'
    
    # Generate molecules and save them
    if args.algorithm == 'rnn':
        df = pd.DataFrame()
        repeat = 1
        batch_size = min(args.num, args.batch_size)
        if args.num > 1048:
            repeat = math.ceil(args.num / batch_size)
        df['Smiles'], scores = agent.evaluate(batch_size, repeat = repeat, method=env)
        scores = pd.concat([df, scores],axis=1)
    else:
        # we are currently not saving the generated smiles (for encoder decoder models) only their scores
        frags, smiles, scores = agent.evaluate(loader, repeat=args.num, method=env)
        scores['Frags'], scores['SMILES'] = frags, smiles
    scores.to_csv(out, index=False, sep='\t', float_format='%.2f')


if __name__ == "__main__":
    
    args = DesignArgParser()
    Design(args)
