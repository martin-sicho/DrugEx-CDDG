#!/usr/bin/env python
import os
import sys
import json
import torch

from drugex.corpus.vocabulary import VocGraph, VocSmiles, VocGPT
from drugex.logs.utils import commit_hash, enable_file_logger
from drugex import utils
import argparse
import pandas as pd

from torch.utils.data import DataLoader, TensorDataset

from drugex.training.models import GPT2Model, GraphModel, single_network
from drugex.training.models import encoderdecoder
from drugex.training.models.explorer import SmilesExplorer, GraphExplorer, SmilesExplorerNoFrag

import warnings
warnings.filterwarnings("ignore")

    
def GeneratorArgParser(txt=None):
    """ Define and read command line arguments """
    
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument('-b', '--base_dir', type=str, default='.',
                        help="Base directory which contains folders 'data' (and 'envs')")
    parser.add_argument('-k', '--keep_runid', action='store_true', help="If included, continue from last run")
    parser.add_argument('-p', '--pick_runid', type=int, default=None, help="Used to specify a specific run id")
    parser.add_argument('-d', '--debug', action='store_true')
    
    
    parser.add_argument('-did', '--data_runid', type=str, default=None,
                        help="Run id of the input data files, defaults to current runid")
    parser.add_argument('-i', '--input', type=str, default=None,
                        help="Prefix of input files. If --mode is 'PT', default is 'chembl_4:4_brics' else 'ligand_4:4_brics' ")  
    parser.add_argument('-vfs', '--voc_files', type=str, nargs='*', default=['smiles'],
                        help="Names of voc files to use as vocabulary.")
    parser.add_argument('-o', '--output', type=str, default=None,
                        help="Prefix of output files. If None, set to be the first word of input. ")     
    parser.add_argument('-m', '--mode', type=str, default='RL',
                        help="Mode, of the training: 'PT' for pretraining, 'FT' for fine-tuning and 'RL' for reinforcement learning") 
    
    # Input models 
    parser.add_argument('-pt', '--pretrained_model', type=str, default=None,
                        help="Name of input model (w/o .pkg extension) used as starting point of FT.")
    parser.add_argument('-ag', '--agent_model', type=str, default=None,
                        help="Name of model (w/o .pkg extension) used for the agent in RL.")
    parser.add_argument('-pr', '--prior_model', type=str, default=None,
                        help="Name of model (w/o .pkg extension) used for the prior in RL.")
    
    parser.add_argument('-v', '--version', type=int, default=3,
                         help="DrugEx version")
    
    # General parameters
    parser.add_argument('-a', '--algorithm', type=str, default='graph',
                        help="Generator algorithm: 'graph' for graph-based algorithm (transformer),or "\
                             "'gpt' (transformer), 'ved' (lstm-based encoder-decoder)or "\
                             "'attn' (lstm-based encoder-decoder with attention mechanism) for SMILES-based algorithm ")
    parser.add_argument('-e', '--epochs', type=int, default=1000,
                        help="Number of epochs")
    parser.add_argument('-bs', '--batch_size', type=int, default=256,
                        help="Batch size")
    parser.add_argument('-gpu', '--gpu', type=str, default='1,2,3,4',
                        help="List of GPUs") 

    
    # RL parameters
    parser.add_argument('-eps', '--epsilon', type=float, default=0.1,
                        help="Exploring rate")
    parser.add_argument('-bet', '--beta', type=float, default=0.0,
                        help="Reward baseline")
    parser.add_argument('-s', '--scheme', type=str, default='PR',
                        help="Reward calculation scheme: 'WS' for weighted sum, 'PR' for Pareto front or 'CD' for 'PR' with crowding distance")

    parser.add_argument('-eid', '--env_runid', type=str, default=None,
                        help='Run id of the environment-predictor models, defaults to current runid')
    parser.add_argument('-et', '--env_task', type=str, default='CLS',
                        help="Environment-predictor task: 'REG' or 'CLS'")
    parser.add_argument('-ea', '--env_alg', type=str, default='RF',
                        help="Environment-predictor algorith: 'RF', 'XGB', 'DNN', 'SVM', 'PLS', 'NB', 'KNN', 'MT_DNN'")
    parser.add_argument('-at', '--activity_threshold', type=float, default=6.5,
                        help="Activity threshold")
    
    parser.add_argument('-qed', '--qed', action='store_true',
                        help="If on, QED is used in desirability function")
    parser.add_argument('-ras', '--ra_score', action='store_true',
                        help="If on, Retrosynthesis Accessibility score is used in desirability function")
    parser.add_argument('-ras_model', '--ra_score_model', type=str, default='XBG',
                        help="RAScore model: 'XBG'")
    parser.add_argument('-mw', '--molecular_weight', action='store_true',
                        help='If on, large compounds are penalized in the desirability function')
    parser.add_argument('-mw_ths', '--mw_thresholds', type=int, nargs='*', default=[500, 1000],
                        help='Thresholds used calculate molecular weight clipped scores in the desirability function.')
    parser.add_argument('-logP', '--logP', action='store_true',
                        help='If on, compounds with large logP values are penalized in the desirability function')
    parser.add_argument('-logP_ths', '--logP_thresholds', type=float, nargs='*', default=[4, 6],
                        help='Thresholds used calculate logP clipped scores in the desirability function')
    
    parser.add_argument('-ta', '--active_targets', type=str, nargs='*', default=[], #'P29274', 'P29275', 'P30542','P0DMS8'],
                        help="Target IDs for which activity is desirable")
    parser.add_argument('-ti', '--inactive_targets', type=str, nargs='*', default=[],
                        help="Target IDs for which activity is undesirable")
    
    parser.add_argument('-ng', '--no_git', action='store_true',
                        help="If on, git hash is not retrieved")

    
    # Load some arguments from string --> usefull functions called eg. in a notebook
    if txt:
        args = parser.parse_args(txt)
    else:
        args = parser.parse_args()

    # Default input file prefix in case of pretraining and finetuning
    if args.input is None:
        if args.mode == 'PT':
            args.input = 'chembl_4:4_brics'
        else:
            args.input = 'ligand_4:4_brics'
            
    # Setting output file prefix from input file
    if args.output is None:
        args.output = args.input.split('_')[0]

    if args.version == 2:
        args.algorithm = 'rnn'
    
#     if args.mode == 'FT':
#         #In case of FT setting some parameters from PT parameters
#         with open(args.base_dir + '/generators/' + args.pretrained_model + '.json') as f:
#             pt_params = json.load(f)
#         args.algorithm = pt_params['algorithm']
#     elif args.mode == 'RL':
#         #In case of RL setting some parameters from FT parameters
#         with open(args.base_dir + '/generators/' + args.finetuned_model + '.json') as f:
#             pt_params = json.load(f)
#         args.algorithm = pt_params['algorithm']
    
    args.targets = args.active_targets + args.inactive_targets

    return args


def getVocFromFiles(paths, voc_class, *args, **kwargs):
    vocs = [voc_class.fromFile(path, *args, **kwargs) for path in paths]
    if len(vocs) > 1:
        return sum(vocs[1:], start=vocs[0])
    else:
        return vocs[0]


def LoadEncodedMoleculeFragmentPairs(data_path, input_prefix, subset, mol_type, runid='0000'):
    
    """ 
    Load fragment-based input data to dataframe.
    
    Arguments:
        data_path (str)            : folder containing input files
        input_prefix (str)         : prefix of input file
        subset (str)               : subset name : 'train', 'unique' or 'test'
        mol_type (str)             : molecule representation type : 'graph' or 'smi'
        runid (str), opt           : runid of input file
    Returns:
        data (pd.DataFrame)        : dataframe containing encoded molecule-fragement pairs
    """
    
    path =  data_path + '_'.join([input_prefix, subset, mol_type, runid]) + '.txt'
    
    try:
        data = pd.read_table(path)
    except:
        path_def =  data_path  + '_'.join([input_prefix, subset, mol_type]) + '.txt'
        logSettings.log.warning('Reading %s instead of %s' % (path_def, path))
        data = pd.read_table(path_def)
        
    return data

def DataPreparationGraph(voc_files, base_dir, runid, input_prefix, batch_size=128, unique_frags=False):
    """
    Reads and preprocesses the vocabulary and input data for a graph-based generator
    
    Arguments:
        base_dir (str)              : name of the folder containing 'data' folder with input files
        runid (str)                 : runid, suffix of the input files
        input_prefix (str)          : prefix of input files
        batch_size (int), opt       : batch size
        unique_frags (bool), opt    : if True, uses reduced training set containing only unique fragment-combinations
    Returns:
        voc                         : atom vocabulary
        train_loader                : torch DataLoader containing training data
        valid_loader                : torch DataLoader containing validation data
    """
    
    data_path = base_dir + '/data/'
    mol_type = 'graph'
    
    # Set vocabulary
    try: 
        voc = getVocFromFiles(
            [data_path + f"{v}_graph_{logSettings.runID}.txt" for v in voc_files],
            VocGraph,
            max_len=80, n_frags=4
        )
    except FileNotFoundError:
        logSettings.log.warning('Reading voc_graph.txt instead of voc_graph_%s.txt' % runid)
        voc = getVocFromFiles(
            [data_path + "voc_graph.txt"],
            VocGraph,
            max_len=80, n_frags=4
        )
    
    # Load train data
    data = LoadEncodedMoleculeFragmentPairs(data_path, input_prefix, 
                                            'unique' if unique_frags else 'train', 
                                            mol_type, runid)
    data = torch.from_numpy(data.values).long().view(len(data), voc.max_len, -1)
    train_loader = DataLoader(data, batch_size=batch_size * 4, drop_last=False, shuffle=True)

    # Load test data
    test = LoadEncodedMoleculeFragmentPairs(data_path, input_prefix, 'test', mol_type, runid)        
    test = torch.from_numpy(test.values).long().view(len(test), voc.max_len, -1)
    valid_loader = DataLoader(test, batch_size=batch_size * 10, drop_last=False, shuffle=True)
    
    return voc, train_loader, valid_loader

def DataPreparationSmiles(voc_files, base_dir, runid, input_prefix, batch_size=128, unique_frags=False):
    
    """
    Reads and preprocesses the vocabulary and input data for a graph-based generator
    
    Arguments:
        base_dir (str)              : name of the folder containing 'data' folder with input files
        runid (str)                 : runid, suffix of the input files
        input_prefix (str)          : prefix of input files
        batch_size (int), optional  : batch size
        unique_frags (bool), opt    : if True, uses reduced training set containing only unique fragment-combinations
    Returns:
        voc                         : atom vocabulary
        train_loader                : torch DataLoader containing training data
        valid_loader                : torch DataLoader containing validation data
    """
    
    data_path = base_dir + '/data/'
    mol_type = 'smi'
    
    # Set vocabulary
    paths = [data_path + f'{x}_smiles_{runid}.txt' for x in voc_files]
    if args.algorithm == 'gpt':
        try:
            voc = getVocFromFiles(
                paths,
                VocGPT,
                src_len=100, trg_len=100
            )
        except FileNotFoundError:
            logSettings.log.warning('Reading voc_smiles.txt instead of voc_smiles_%s.txt' % runid)
            voc = getVocFromFiles([data_path + 'voc_smiles.txt'], VocGPT, src_len=100, trg_len=100)
    else:
        try:
            voc = getVocFromFiles(
                paths,
                VocSmiles,
                max_len=100
            )
        except FileNotFoundError:
            logSettings.log.warning('Reading voc_smiles.txt instead of voc_smiles_%s.txt' % runid)
            voc = getVocFromFiles([data_path + 'voc_smiles.txt'], VocSmiles, max_len=100)

    # Without input fragments
    if args.algorithm == 'rnn':
        try:
            data = pd.read_table( data_path + f'{input_prefix}_{runid}.txt')
        except FileNotFoundError:
            logSettings.log.warning('Reading %s.txt instead of %s_%s.txt' % (input_prefix, input_prefix, runid))
            data = pd.read_table( data_path + '%s.txt' % input_prefix)

        # split data into train and test set (for dnn originally only done during fine-tuning)
        # test size is 10% of training, with a maximum of 10 000 
        test_size = min(len(data) // 10, int(1e4))
        if len(data) // 10 > int(1e4):
            logSettings.log.warning('To speed up the training, the test set is reduced to a random sample of 10 000 compounds from the original test !')
        test = data.sample(test_size).Token
        train = data.drop(test.index).Token

        train_set = torch.LongTensor(voc.encode([seq.split(' ') for seq in train]))
        test_set = torch.LongTensor(voc.encode([seq.split(' ') for seq in test]))
        valid_loader = DataLoader(test_set, batch_size=batch_size, shuffle=True)
    
    # With input fragments
    else:
        # Load train data
        train = LoadEncodedMoleculeFragmentPairs(data_path, input_prefix, 
                                                'unique' if unique_frags else 'train', 
                                                mol_type, runid)
        train_in = voc.encode([seq.split(' ') for seq in train.Input.values])
        train_out = voc.encode([seq.split(' ') for seq in train.Output.values])
        train_set = TensorDataset(train_in, train_out)

        # Load test data
        test = LoadEncodedMoleculeFragmentPairs(data_path, input_prefix, 'test', mol_type, runid)     
        test = test.Input.drop_duplicates()
        test_set = voc.encode([seq.split(' ') for seq in test])
        test_set = utils.TgtData(test_set, ix=[voc.decode(seq, is_tk=False) for seq in test_set])
        valid_loader = DataLoader(test_set, batch_size=batch_size, collate_fn=test_set.collate_fn)

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
    
    return voc, train_loader, valid_loader


def InitializeEvolver(agent, prior, algorithm, batch_size, epsilon, beta, scheme):
    
    """
    Sets up the evolver composed of two generators.
    
    Arguments:        
        agent (torch model)         : main generator that is optimized during training
        prior (torch model)         : mutation generator is kept frozen during the process
        algorithm (str)             : name of the generator algorithm
        batch_size (int)            : batch size
        epsilon (float)             : exploration rate
        beta (float)                : reward baseline
        scheme (str)                : name of optimization scheme
    Returns:
        evolver (torch model)       : evolver composed of two generators
    """
    
    if algorithm == 'graph':
        evolver = GraphExplorer(agent, mutate=prior)
    elif algorithm == 'rnn':
        evolver = SmilesExplorerNoFrag(agent, prior, agent)
    else:
        evolver = SmilesExplorer(agent, mutate=prior)
        
    evolver.batch_size = batch_size 
    evolver.epsilon = epsilon 
    evolver.sigma = beta 
    evolver.scheme = scheme 
    evolver.repeat = 1   
    
    return evolver
    

def CreateDesirabilityFunction(base_dir, 
                               alg, 
                               task, 
                               scheme, 
                               env_runid,
                               active_targets=[], 
                               inactive_targets=[], 
                               activity_threshold=6.5, 
                               qed=False, 
                               ra_score=False, 
                               ra_score_model='XBG',
                               mw=False,
                               mw_ths=[500,1000],
                               logP=False,
                               logP_ths=[4,6]):
    
    """
    Sets up the objectives of the desirability function.
    
    Arguments:
        base_dir (str)              : folder containing 'envs' folder with saved environment-predictor models
        alg (str)                   : environment-predictor algoritm
        task (str)                  : environment-predictor task: 'REG' or 'CLS'
        scheme (str)                : optimization scheme: 'WS' for weighted sum, 'PR' for Parento front with Tanimoto-dist. or 'CD' for PR with crowding dist.
        env_runid (str)             : runid of the environment-predictor model
        active_targets (lst), opt   : list of active target IDs
        inactive_targets (lst), opt : list of inactive target IDs
        activity_threshold (float), opt : activety threshold in case of 'CLS'
        qed (bool), opt             : if True, 'quantitative estimate of drug-likeness' included in the desirability function
        ra_score (bool), opt        : if True, 'Retrosythesis Accessibility score' included in the desirability function
        ra_score_model (str), opt   : RAscore algorithm: 'NN' or 'XGB'
        mw (bool), opt              : if True, large molecules are penalized in the desirability function
        mw_ths (list), opt          : molecular weight thresholds to penalize large molecules
        logP (bool), opt            : if True, molecules with logP values are penalized in the desirability function
        logP_ths (list), opt        : logP thresholds to penalize large molecules
    
    Returns:
        objs (lst)                  : list of selected predictors 
        keys (lst)                  : list of names of selected predictors
        mods (lst)                  : list of ClippedScore-functions per predictor
        ths (lst)                   : list desirability thresholds per predictor
        
    """
    
    objs, keys = [], []
    targets = active_targets + inactive_targets
    
    for t in targets:
        if alg.startswith('MT_'):
            sys.exit('TO DO: using multitask model')
        else:
            try :
                path = base_dir + '/envs/single/' + '_'.join([alg, task, t, env_runid]) + '.pkg'
                objs.append(utils.Predictor(path, type=task))
            except FileNotFoundError:
                path_false = base_dir + '/envs/single/' + '_'.join([alg, task, t, env_runid]) + '.pkg'
                path = base_dir + '/envs/single/' + '_'.join([alg, task, t]) + '.pkg'
                logSettings.log.warning('Using model from {} instead of model from {}'.format(path, path_false))
                objs.append(utils.Predictor(path, type=task))
        keys.append(t)
    if qed :
        objs.append(utils.Property('QED'))
        keys.append('QED')
    if ra_score:
        from drugex.training.models.ra_scorer import RetrosyntheticAccessibilityScorer
        objs.append(RetrosyntheticAccessibilityScorer(use_xgb_model=False if ra_score_model == 'NN' else True ))
        keys.append('RAscore')
    if mw:
        objs.append(utils.Property('MW'))
        keys.append('MW')
    if logP:
        objs.append(utils.Property('logP'))
        keys.append('logP')
        
    pad = 3.5
    if scheme == 'WS':
        # Weighted Sum (WS) reward scheme
        if task == 'CLS':
            active = utils.ClippedScore(lower_x=0.2, upper_x=0.5)
            inactive = utils.ClippedScore(lower_x=0.8, upper_x=0.5)
        else:
            active = utils.ClippedScore(lower_x=activity_threshold - pad, upper_x=activity_threshold + pad)
            inactive = utils.ClippedScore(lower_x=activity_threshold + pad, upper_x=activity_threshold - pad)
        ths = [0.5] * (len(targets)) 
            
    else:
        # Pareto Front (PR) or Crowding Distance (CD) reward scheme
        if task == 'CLS':
            active = utils.ClippedScore(lower_x=0.2, upper_x=0.5)
            inactive = utils.ClippedScore(lower_x=0.8, upper_x=0.5)
        else:
            active = utils.ClippedScore(lower_x=activity_threshold - pad, upper_x=activity_threshold)
            inactive = utils.ClippedScore(lower_x=activity_threshold + pad, upper_x=activity_threshold)
        ths = [0.99] * len((targets))
        
        
    mods = []
    for k in keys:
        if k in active_targets: 
            mods.append(active)
        elif k in inactive_targets: 
            mods.append(inactive)
        elif k == 'QED' : 
            mods.append(utils.ClippedScore(lower_x=0, upper_x=1.0)) 
            ths += [0.0]
        elif k == 'RAscore':
            mods.append(utils.ClippedScore(lower_x=0, upper_x=1.0))
            ths += [0.0]
        elif k == 'MW':
            mods.append(utils.ClippedScore(lower_x=mw_ths[1], upper_x=mw_ths[0]))
            ths += [0.5]
        elif k == 'logP':
            mods.append(utils.ClippedScore(lower_x=logP_ths[1], upper_x=logP_ths[0]))
            ths += [0.5]       
    
    return objs, keys, mods, ths

def SetGeneratorAlgorithm(voc, alg):
    
    """
    Initializes the generator algorithm
    
    Arguments:
        voc (): vocabulary
        alg (str): molecule format type: 'ved', 'attn', 'gpt' or 'graph'
    Return:
        agent (torch model): molecule generator 
    """
    
    if alg == 'ved':
        agent = encoderdecoder.EncDec(voc, voc).to(utils.dev)
    elif alg == 'attn':
        agent = encoderdecoder.Seq2Seq(voc, voc).to(utils.dev)
    elif alg == 'gpt':
        agent = GPT2Model(voc, n_layer=12).to(utils.dev)
    elif alg == 'graph':
        agent = GraphModel(voc).to(utils.dev)
    elif alg == 'rnn':
        ## add argument for is_lstm
        agent = single_network.RNN(voc, is_lstm=True)
    
    return agent

def PreTrain(args):
    
    """
    Wrapper to pretrain a generator
    
    Arguments:
        args (NameSpace): namespace containing command line arguments
    """
    
    pt_path = args.base_dir + '/generators/' + args.output + '_' + args.algorithm + '_' + args.runid
        
    print('Loading data from {}/data/{}'.format(args.base_dir, args.input))
    if args.algorithm == 'graph':
        voc, train_loader, valid_loader = DataPreparationGraph(args.voc_files, args.base_dir, args.data_runid, args.input, args.batch_size)
        print('Pretraining graph-based model ...')
    else:
        voc, train_loader, valid_loader = DataPreparationSmiles(args.voc_files, args.base_dir, args.data_runid, args.input, args.batch_size)
        print('Pretraining SMILES-based ({}) model ...'.format(args.algorithm))
    
    agent = SetGeneratorAlgorithm(voc, args.algorithm)
    agent.fit(train_loader, valid_loader, epochs=args.epochs, out=pt_path)
        
def FineTune(args):
    
    """
    Wrapper to finetune a generator
    
    Arguments:
        args (NameSpace): namespace containing command line arguments
    """
    
    if args.pretrained_model :
        pt_path = args.base_dir + '/generators/' + args.pretrained_model + f'_{args.algorithm}_{args.runid}.pkg'
    else:
        raise ValueError('Missing --pretrained_model argument')
    
    args.finetuned_model = args.output + '_' + args.algorithm + '_' + args.runid
    ft_path = args.base_dir + '/generators/' + args.finetuned_model
        
    print('Loading data from {}/data/{}'.format(args.base_dir, args.input))
    if args.algorithm == 'graph':
        voc, train_loader, valid_loader = DataPreparationGraph(args.voc_files, args.base_dir, args.data_runid, args.input, args.batch_size)
        print('Fine-tuning graph-based model ...')
    else:
        voc, train_loader, valid_loader = DataPreparationSmiles(args.voc_files, args.base_dir, args.data_runid, args.input, args.batch_size)
        print('Fine-tuning SMILES-based ({}) model ...'.format(args.algorithm))
    
    agent = SetGeneratorAlgorithm(voc, args.algorithm)
    agent.load_state_dict(torch.load(pt_path, map_location=utils.dev))
    agent.fit(train_loader, valid_loader, epochs=args.epochs, out=ft_path)
      
    
def RLTrain(args):
    
    """
    Wrapper for the Reinforcement Learning
    
    Arguments:
        args (NameSpace): namespace containing command line arguments
    """
    
#     if args.version == 3:
#         # In v3, the agent and prior both use the FT model
#         ft_path = args.base_dir + '/generators/' + args.finetuned_model + '.pkg'
#         pt_path = ft_path
#     else :
#         # In v2, the agent and crover use the FT model and the prior the PT model
#         ft_path = args.base_dir + '/generators/' + args.finetuned_model + '.pkg'
#         pt_path = args.base_dir + '/generators/' + args.pretrained_model + '.pkg'

    if not args.targets:
        raise ValueError('At least on active or inactive target should be given for RL.')

    ag_path = args.base_dir + '/generators/' + args.agent_model + f'_{args.algorithm}_{logSettings.runID}.pkg'
    pr_path = args.base_dir + '/generators/' + args.prior_model + f'_{args.algorithm}_{logSettings.runID}.pkg'

    # rl_path = args.base_dir + '/generators/' + '_'.join([args.output, args.algorithm, args.env_alg, args.env_task, 
    #                                                     args.scheme, str(args.epsilon)]) + 'e'
    rl_path = args.base_dir + '/generators/' + '_'.join([args.output, args.algorithm, 'RL', args.runid])
                                                    
    ## why need input for RL? probably because need input in v3 to generate sequences
    print('Loading data from {}/data/{}'.format(args.base_dir, args.input))
    if args.algorithm == 'graph':
        voc, train_loader, valid_loader = DataPreparationGraph(args.voc_files, args.base_dir, args.data_runid, args.input, args.batch_size, unique_frags=True)
    elif args.algorithm != 'rnn':
        voc, train_loader, valid_loader = DataPreparationSmiles(args.voc_files, args.base_dir, args.data_runid, args.input, args.batch_size, unique_frags=True)
    else:
        data_path = args.base_dir + '/data/'
        paths = [data_path + f'{x}_smiles_{logSettings.runID}.txt' for x in args.voc_files]
        try:
            voc = getVocFromFiles(paths, VocSmiles, max_len=100)
        except FileNotFoundError:
            logSettings.log.warning('Reading voc_smiles.txt instead of voc_smiles_%s.txt' % args.runid)
            voc = getVocFromFiles([data_path + 'voc_smiles.txt'], VocSmiles, max_len=100)
    
    # Initialize agent and prior by loading pretrained model
    agent = SetGeneratorAlgorithm(voc, args.algorithm)        
    agent.load_state_dict(torch.load(ag_path, map_location=utils.dev))
    prior = SetGeneratorAlgorithm(voc, args.algorithm)        
    prior.load_state_dict(torch.load(pr_path, map_location=utils.dev))

    # Initialize evolver algorithm
    ## first difference for v2 needs to be adapted
    evolver = InitializeEvolver(agent, prior, args.algorithm, args.batch_size, args.epsilon, args.beta, args.scheme)
    
    # Create the desirability function
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
    
    # Set Evolver's environment-predictor
    evolver.env = utils.Env(objs=objs, mods=mods, keys=keys, ths=ths)
    
    #root = '%s/generators/%s_%s' % (args.base_dir, args.algorithm, time.strftime('%y%m%d_%H%M%S', time.localtime()))
    #os.mkdir(root)

    # No idea what the following lines should do as the files that should be copied does not exist !?!?!?
#     copy2(args.algorithm + '_ex.py', root)
#     copy2(args.algorithm + '.py', root)

    # import evolve as agent
    evolver.out = rl_path #root + '/%s_%s_%s_%.0e' % (args.algorithm, evolver.scheme, args.env_task, evolver.epsilon)
    if args.version == 3 and args.algorithm != 'rnn':
        evolver.fit(train_loader, test_loader=valid_loader, epochs=args.epochs)
    else:
        ## second difference for v2 needs to be adapted
        evolver.fit(epochs=args.epochs)
    
    
    with open(rl_path + '.json', 'w') as fp:
        json.dump(vars(args), fp, indent=4)


def TrainGenerator(args):
    
    """
    Wrapper to train a setup and train a generator
    
    Arguments:
        args (NameSpace): namespace containing command line arguments
    """
   
    if args.no_git is False:
        args.git_commit = commit_hash(os.path.dirname(os.path.realpath(__file__)))
    print(json.dumps(vars(args), sort_keys=False, indent=2))

    utils.devices = eval(args.gpu) if ',' in args.gpu else [eval(args.gpu)]
    torch.cuda.set_device(utils.devices[0])
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu
    
    if not os.path.exists(args.base_dir + '/generators'):
        os.makedirs(args.base_dir + '/generators')  
        
    with open(args.base_dir + '/logs/{}/{}_{}_{}.json'.format(args.runid, args.output, args.algorithm, args.runid), 'w') as f:
        json.dump(vars(args), f)
    
    log = logSettings.log
    if args.mode == 'PT':
        log.info("Pretraining started.")
        try:
            PreTrain(args)
        except Exception as exp:
            log.exception("Something went wrong in the pretraining.")
            raise exp
        log.info("Pretraining finished.")
    elif args.mode == 'FT':
        log.info("Finetuning started.")
        try:
            FineTune(args)
        except Exception as exp:
            log.exception("Something went wrong in the finetuning.")
            raise exp
        log.info("Finetuning finished.")
    elif args.mode == 'RL' :
        log.info("Reinforcement learning started.")
        try:
            RLTrain(args)
        except Exception as exp:
            log.exception("Something went wrong in the finetuning.")
            raise exp
        log.info("Reinforcement learning finised.")
    else:
        raise ValueError("--mode should be either 'PT', 'FT' or 'RL', you gave {}".format(args.mode))

if __name__ == "__main__":
    args = GeneratorArgParser()

    logSettings = enable_file_logger(
        os.path.join(args.base_dir,'logs'),
        'train.log',
        args.keep_runid,
        args.pick_runid,
        args.debug,
        __name__,
        commit_hash(os.path.dirname(os.path.realpath(__file__))) if not args.no_git else None,
        vars(args)
    )

    # Default input file prefix in case of pretraining and finetuning
    if args.data_runid is None:
        args.data_runid = logSettings.runID
        
    if args.env_runid is None:
        args.env_runid = logSettings.runID

    # Create json log file with used commandline arguments 
    print(json.dumps(vars(args), sort_keys=False, indent=2))
    with open('%s/logs/%s/train_args.json' % (args.base_dir, logSettings.runID), 'w') as f:
        json.dump(vars(args), f)

    args.runid = logSettings.runID
    TrainGenerator(args)