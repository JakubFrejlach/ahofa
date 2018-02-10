#!/usr/bin/env python3
# Jakub Semric 2018
# automation of reduction, error computing and state labeling

import sys
import os
import argparse
import subprocess
import tempfile
import re
import datetime
import glob
import random
import math
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

from nfa import Nfa
from reduction import PruneReduction

def search_for_file(fname):
    for root, dirs, files in os.walk('.'):
        if fname in files:
            return os.path.join(root, fname)
    return None

def get_freq(fname):
    ret = {}
    with open(fname, 'r') as f:
        for line in f:
            line = line.split('#')[0]
            if line:
                state, freq, *_ = line.split()
                ret[int(state)] = int(freq)

    return ret

def generate_output(*, folder, filename, extension):
    # generating filename
    while True:
        # random identifier
        hsh = ''.join([str(x) for x in random.sample(range(0, 9), 5)])
        dest = '{}.{}{}'.format(filename, hsh, extension)
        dest = os.path.join(folder, dest)
        if not os.path.exists(dest):
            break

    return dest

def execute_batch(batch_file):
    snortdir= 'min-snort'
    nfadir = 'data/nfa'
    resdir = 'data/prune'

    parser = argparse.ArgumentParser()
    # general
    parser.add_argument('-i', '--input', type=str, nargs='+', help='input NFA')
    parser.add_argument('-n', '--nworkers', type=int, help='number of cores',
        default=1)
    parser.add_argument('-p', '--pcaps', type=str, nargs='+', help='pcap files')
    # what to do
    parser.add_argument('--error', action='store_true', help='compute error')
    parser.add_argument('--reduce', action='store_true', help='reduce')
    # reduction parameters
    parser.add_argument('-t', '--reduction-type', choices=['prune','ga','armc'],
        help='reduction type', default='prune')
    parser.add_argument('-r', '--reduce-to', type=float, nargs='+',
        help='% states', default=[0.1, 0.12, 0.14, 0.16, 0.18, 0.2])
    parser.add_argument(
        '-l','--state-labels', type=str, help='labeled nfa states')

    # remove '#' comments and collect the arguments
    args = list()
    with open(batch_file, 'r') as f:
        for line in f:
            line = line.split('#')[0]
            if line:
                args += line.split()

    args = parser.parse_args(args)
    #print(args)

    nfa_filenames = args.input.copy()

    if args.reduce:
        # compute error with newly reduced NFAs, erase old NFAs
        nfa_filenames = list()
        if args.state_labels == None:
            sys.stderr.write('Error: state frequencies are not specified\n')
            exit(1)

        # generate output file name
        for j in args.input:
            core = os.path.basename(j).split('.')[0]
            for i in args.reduce_to:
                fname = generate_output(folder=nfadir, filename=core,
                    extension='.r' + str(i) + '.fa')
                nfa_filenames.append(fname)
                prog = [str(x) for x in ['./nfa_handler','-r', j,
                    '-p', i, '-o', fname, args.state_labels]]
                sys.stderr.write(' '.join(prog) + '\n')
                # invoke program for reduction
                subprocess.call(prog)



    if args.error:
        # get pcap files
        samples = set()
        for i in args.pcaps:
            samples |= set(glob.glob(i))

        # find target nfas to each input nfa
        for i in nfa_filenames:
            core = os.path.basename(i).split('.')[0]
            target_str = os.path.join(snortdir, core)
            # find target NFA file name
            target_nfa = glob.glob(target_str + '*.fa')
            if len(target_nfa) == 0:
                sys.stderr.write('Error: cannot find "' + target_str +'*.fa"\n')
                continue
            # get first occurrence
            target_nfa = target_nfa[0]
            # generate output file name
            output = generate_output(folder=resdir, filename=core,
                extension='.json')

            #prog = [str(x) for x in ['./nfa_handler', target_nfa, i,
            #    '-o', output,'-n', args.nworkers]] + list(samples)
            # TODO -o resdir
            prog = [str(x) for x in ['./nfa_handler', target_nfa, i,
                '-s','-n', args.nworkers]] + list(samples)
            sys.stderr.write(' '.join(prog) + '\n')
            # invoke program for error computation
            subprocess.call(prog)

def write_output(fname, buf):
    if fname:
        with open(fname, 'w') as f:
            for i in buf:
                f.write(i)
    else:
        for i in buf:
            print(i, end='')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--batch', type=str, help='use batch file')

    # general arguments
    # common reduction arguments
    general_parser = argparse.ArgumentParser(add_help=False)
    general_parser.add_argument(
        '-o','--output', type=str, metavar='FILE',
        help='output file, if not specified output is printed to stdout')

    nfa_input_parser = argparse.ArgumentParser(add_help=False)
    nfa_input_parser.add_argument('input', metavar='NFA', type=str)

    # 4 commands for NFA
    subparser = parser.add_subparsers(
        help='command', dest='command')

    # reduction
    reduce_parser = subparser.add_parser(
        'reduce', help='NFA reduction',
        parents = [general_parser, nfa_input_parser])
    reduce_parser.add_argument(
        '-f','--freq',type=str,help='packets frequencies')

    # rabit tool
    rabit_parser = subparser.add_parser(
        'issubset', help='if L(NFA1) is subset of L(NFA2)',
        parents = [general_parser])
    rabit_parser.add_argument('NFA1', type=str)
    rabit_parser.add_argument('NFA2', type=str)

    # reduce tool
    min_parser = subparser.add_parser(
        'min', help='minimizes NFA by bisimulation',
        parents = [general_parser, nfa_input_parser])

    # dot format and jpg format
    dot_parser = subparser.add_parser(
        'dot', help='draw NFA',
        parents = [general_parser, nfa_input_parser])
    dot_parser.add_argument('-f', '--freq', type=str, help='heat map')
    dot_parser.add_argument(
        '-t', '--trans', action='store_true',
        help='show transition labels')
    dot_parser.add_argument(
        '-s', '--show', action='store_true', help='show result')

    # light-weight minimization
    lmin_parser = subparser.add_parser(
        'lmin', help='minimizes NFA by light-weight minimization',
        parents = [general_parser, nfa_input_parser])

    # some statistics about the NFA
    nfastats_parser = subparser.add_parser(
        'stats', help='prints some statistics about the automaton',
        parents = [general_parser, nfa_input_parser])
    nfastats_parser.add_argument(
        '-f','--freq', action='store_true', help='packet frequency histogram')
    nfastats_parser.add_argument(
        '-d','--depth', action='store_true', help='state depth histogram')
    nfastats_parser.add_argument(
        '-m','--max', type=int, help='maximal boundary value to display')
    nfastats_parser.add_argument(
        '-t','--topn', type=int, help='show top N statistics', metavar='N',
        default=5)
    nfastats_parser.add_argument(
        '-r','--rules', action='store_true', help='show top N statistics')

    args = parser.parse_args()
    if args.command == None and args.batch == None:
        sys.stderr.write("Error: no arguments\n")
        sys.stderr.write("Use '--help' or '-h' for help.\n")
        exit(1)
    elif args.batch:
        sys.stderr.write('executing batch file\n')
        execute_batch(args.batch)
        exit(0)

    if args.command == 'min':
        jarfile = search_for_file('Reduce.jar')
        if jarfile == None:
            sys.stderr.write(
                'Error: cannot find Reduce tool in this directory\n')
            sys.exit(1)
        if not args.output:
            sys.stderr.write('Error: no output specified\n')
            exit(1)
        ba_file = tempfile.NamedTemporaryFile()
        reduce_file = tempfile.NamedTemporaryFile()

        aut = Nfa.parse(args.input, 'fa')
        mapping = aut.extend_final_states()
        write_output(ba_file.name, aut.write(how='ba'))

        proc = "java -jar " + jarfile + " " + ba_file.name + \
        " 10 -sat -finite -o " + reduce_file.name
        subprocess.call(proc.split())
        aut = Nfa.parse(reduce_file.name, 'ba')

        aut.retrieve_final_states(mapping)
        # rename states
        max_label = max(aut.states) + 1
        vals = set(mapping.values())
        for s in aut.states:
            if s in vals:
                mapping[s] = max_label
                max_label += 1

        aut.rename_states(mapping)
        write_output(args.output, aut.write())
    elif args.command == 'issubset':
        jarfile = search_for_file('RABIT.jar')
        if jarfile == None:
            sys.stderr.write(
                'Error: cannot find RABIT tool in this directory\n')
            sys.exit(1)
        aut1 = Nfa.parse(args.NFA1)
        aut2 = Nfa.parse(args.NFA2)
        aut1.selfloop_to_finals()
        aut2.selfloop_to_finals()
        aut1_ba = tempfile.NamedTemporaryFile()
        aut2_ba = tempfile.NamedTemporaryFile()
        aut1.print(open(aut1_ba.name,'w'), how='ba')
        aut2.print(open(aut2_ba.name,'w'), how='ba')

        proc = 'java -jar ' + jarfile + ' ' + aut1_ba.name + ' ' + \
        aut2_ba.name + ' -fast -finite'
        subprocess.call(proc.split())
    elif args.command == 'lmin':
        aut = Nfa.parse(args.input)
        aut.lightweight_minimization()
        gen = aut.write()
        write_output(args.output, gen)
    elif args.command == 'dot':
        _freq = None
        if args.freq:
            _freq = get_freq(args.freq)
        aut = Nfa.parse(args.input)
        gen = aut.write_dot(show_trans=args.trans, freq=_freq)
        fname = args.output if args.output else 'dot'
        write_output(fname, gen)
        if args.show:
            image = fname.split('.dot')[0] + '.jpg'
            prog = 'dot -Tjpg ' + fname + ' -o ' + image
            subprocess.call(prog.split())
            prog = 'xdg-open ' + image
            subprocess.call(prog.split())
    elif args.command == 'stats':
        if args.freq:
            dc = get_freq(args.input)
            state_cnt = len(dc)
            plt.xlabel('number of packets')
            plt.ylabel('number of states')
            print('packets frequency top ', args.topn, ':')
            print('packets\t\tstates\t\tpct%')
        else:
            aut = Nfa.parse(args.input)
            state_cnt = aut.state_count
            if args.depth:
                dc = aut.state_depth
                plt.xlabel('depth')
                plt.ylabel('states')
                print('depth count top ', args.topn, ':')
                print('depth\t\tstates\t\tpct%')
            elif args.rules:
                rules = aut.split_to_rules()
                total = 0
                for rule in rules.values():
                    print(rule)
                    total += len(rule)
                print('total: {} rules:{}'.format(aut.state_count,total))
                return
            else:
                dc = aut.neigh_count()
                plt.xlabel('number of neighbors')
                plt.ylabel('number of states')
                print('neighbors count top ', args.topn, ':')
                print('neighbors\tstates\t\tpct%')

        # textual stats about distribution
        dist = defaultdict(int)
        for i in dc.values():
            dist[i] += 1

        srt_keys = sorted(dist.keys(),key=lambda x: -dist[x])
        total = 0
        total_pct=0

        print('='*40)
        for i in range(min(len(srt_keys), args.topn)):
            n_neigh = srt_keys[i]
            cnt = dist[n_neigh]
            total += cnt
            pct = round(100 * cnt / state_cnt, 2)
            total_pct += pct
            print('{}\t\t{}\t\t{}'.format(n_neigh, cnt, pct))

        print('='*40)
        print('\t\t{}\t\t{}'.format(total,round(total_pct,2)))

        # plot a histogram
        vals = list(dc.values())
        if args.max:
            plt.hist(vals, range=(0,args.max))
        else:
            plt.hist(vals)
        plt.show()
    elif args.command == 'reduce':
        aut = Nfa.parse(args.input)
        with open(args.freq, 'r') as f:
            mx = np.loadtxt(f, delimiter=' ')
        mx = mx / mx.max()
        #print(aut.eval_states(mx))
        #return
        '''
        reduction = CorrReduction(aut, 0.3)
        reduction.evaluate_states(args.freq)
        reduction.reduce(verbose=True)
        gen = aut.write()
        write_output(args.output, gen)
        '''
        
        #val = {key : v * 100000 for key,v in val.items()}
        val = aut.eval_states(mx)
        #write_output(args.output, aut.write_dot(freq=val))
        write_output('aut.dot', aut.write_dot(freq=val))
        subprocess.call('dot -Tjpg aut.dot -o aut.jpg'.split())
        subprocess.call('xdg-open aut.jpg'.split())
        

        #reduction = CorrReduction(aut, 0.3)
        #reduction.evaluate_states()
        return
        reduction = PruneReduction(aut, 0.3)
        reduction.evaluate_states(args.freq)
        reduction.reduce(verbose=True)
        gen = aut.write()
        write_output(args.output, gen)
    else:
        assert False

if __name__ == "__main__":
    main()
