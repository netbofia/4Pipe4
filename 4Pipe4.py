#!/usr/bin/python3
# Copyright 2011-2015 Francisco Pina Martins <f.pinamartins@gmail.com>
# This file is part of 4Pipe4.
# 4Pipe4 is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# 4Pipe4 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with 4Pipe4.  If not, see <http://www.gnu.org/licenses/>.

import subprocess
import os
import sys
import shutil
import time
import configparser
import TCSfilter as TCS
import SNPgrabber as SNPg
import ORFmaker
import Reporter
import SSRfinder as ssr
import Metrics
import SAM_to_BAM
import BAM_to_TCS
import argparse
import sff_extractor
from argparse import RawTextHelpFormatter


# # # # # ARGUMENT LIST # # # # # #
parser = argparse.ArgumentParser(description="",
                                 epilog="The idea here is that to resume an \
analysis that was interrupted for example after the assembling process you \
should issue -s '4,5,6,7,8,9' or -s '456789'. Note that some steps depend on \
the output of previous steps, so using some combinations can cause errors. \
The arguments can be given in any order.",
                                 prog="4Pipe4",
                                 formatter_class=RawTextHelpFormatter)
parser.add_argument("-i", dest="infile", nargs=1, required=True,
                    help="Provide the full path to your target sff file\n",
                    metavar="sff_file")
parser.add_argument("-o", dest="outfile", nargs=1, required=True,
                    help="Provide the full path to your results directory, \
plus the name you want to give your results\n",
                    metavar="basefile")
parser.add_argument("-c", dest="configFile", nargs=1,
                    help="Provide the full path to your configuration file. \
If none is provided, the program will look in the current working directory \
and  then in ~/.config/4Pipe4rc (in this order) for one. If none is found the \
program will stop\n", metavar="configfile")
parser.add_argument("-s", dest="run_list", nargs="?",
                    default="1 2 3 4 5 6 7 8 9", help="Specify the numbers \
corresponding to the pipeline steps that will be run. The string after -s \
must be given inside quotation marks, and numbers can be joined together or \
separated by any symbol. The numbers are the pipeline steps that should be \
run. This is an optional argument and it's omission will run all steps by \
default. The numbers, from 1 to 9 represent the following steps:\n\t1 - SFF \
extraction\n\t2 - SeqClean\n\t3 - Mira\n\t4 - DiscoveryTCS\n\t5 - \
SNP grabber\n\t6 - ORF finder\n\t7 - Blast2go\n\t8 - SSR finder\n\t9 - 7zip \
the report")
arg = parser.parse_args()


def loading(current_state, size, prefix, width):
    """ Function that prints the loading progress of the script! """
    percentage = int(((current_state+1)/size)*100)
    complete = int(width*percentage*0.01)
    if percentage == 100:
        sys.stdout.write("\r%s [%s%s] %s%% -- Done!\n" % (prefix, "#"*complete,
                         "."*(width-complete), percentage))
    else:
        sys.stdout.write("\r%s [%s%s] %s%%" % (prefix, "#"*complete,
                         "."*(width-complete), percentage))
    sys.stdout.flush()


def StartUp():
    basefile = os.path.abspath("".join(arg.outfile))
    sff = os.path.abspath("".join(arg.infile))
    if arg.configFile is not None:
        rcfile = os.path.abspath("".join(arg.configFile))
    elif os.path.isfile('4Pipe4rc'):
        rcfile = os.path.abspath('4Pipe4rc')
        print("No config file provided, falling back to current working \
              dir 4Pipe4rc")
    elif os.path.isfile(os.path.expanduser('~/.config/4Pipe4rc')):
        rcfile = os.path.abspath(os.path.expanduser('~/.config/4Pipe4rc'))
        print("No config file provided, falling back to ~/.config/4Pipe4rc")
    else:
        print("\nERROR:No config file provided nor found in the standard \
              locations.\n")
        quit("Please run 4Pipe4.py -h for help with running the pipeline.")
    try:
        config = configparser.ConfigParser()
        config.read(rcfile)
    except:
        print("\nERROR: Invalid configuration file\n")
        quit("Please run 4Pipe4.py -h for help with running the pipeline.")
    return basefile, sff, config


def SysPrep(basefile):
    '''Function for prepairing the system for the pipeline.'''
    if os.path.isdir(basefile):
        print("\nThe path used for the basefile points to a directory! \
              Please use a file.\n")
        quit("Please run 4Pipe4.py -h for help with running the pipeline.")
    basepath = os.path.split(basefile)
    if os.path.isdir(basepath[0]):
        os.chdir(basepath[0])
        return basepath[1]
    else:
        print("\nThe directory path used for the basefile does not exist.\n")
        quit("Please run 4Pipe4.py -h for help with running the pipeline.")


def RunProgram(cli, requires_output):
    '''Function for running external programs and dealing with their output.'''
    program_stdout = []
    try:
        program = subprocess.Popen(cli, bufsize=64, shell=False,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        for lines in program.stdout:
            lines = lines.decode("utf-8").strip()
            print(lines)
            program_stdout.append(lines)
    except:
        quit("\nERROR:Program not found... exiting. Check your configuration \
             file.\n")
    if requires_output == 1:
        return program_stdout
    time.sleep(5)


def SffExtraction(sff, basefile):
    '''Function for using the sff_extractor module. It will look for an "ideal"
    clipping value using multiple runs before outputting the final files.'''
    clip_found = 0

    # Sff_extractor parameters:
    sff_config = {}
    sff_config["append"] = False
    sff_config["qual_fname"] = basefile + ".fasta.qual"
    sff_config["want_fastq"] = False
    sff_config["min_leftclip"] = 0
    sff_config["min_freq"] = int(config.get('Variables', 'max_equality'))
    sff_config["xml_info"] = None
    sff_config["want_fr"] = False
    sff_config["pelinker_fname"] = ""
    sff_config["mix_case"] = True
    sff_config["clip"] = True
    sff_config["xml_fname"] = basefile + ".xml"
    sff_config["basename"] = basefile
    sff_config["seq_fname"] = basefile + ".fasta"

    while clip_found < 2:
        extra_clip = sff_extractor.extract_reads_from_sff(sff_config, [sff])
        sff_config["min_leftclip"] += extra_clip
        if extra_clip == 0:
            clip_found += 1
        else:
            clip_found = 0

    print("Sff_extractor finished with a min_left_clip=" +
          str(sff_config["min_leftclip"]) + ".\n")

    return


def SeqClean(basefile):
    '''Function for using seqclean and clean2qual.'''
    # seqclean
    cli = [config.get('Program paths', 'seqclean_path'),
           basefile + '.fasta', '-r', basefile + '.clean.rpt', '-l',
           config.get('Variables', 'min_len'), '-o',
           basefile + '.clean.fasta', '-c',
           config.get('Variables', 'seqcores'), '-v',
           config.get('Program paths', 'UniVecDB_path')]
    print("\nRunning Seqclean using the following command:")
    print(' '.join(cli))
    RunProgram(cli, 0)
    # cln2qual
    cli = [config.get('Program paths', 'cln2qual_path'),
           basefile + '.clean.rpt', basefile + '.fasta.qual']
    print("\nRunning cln2qual using the following command:")
    print(' '.join(cli))
    RunProgram(cli, 0)
    shutil.move(basefile + '.fasta.qual.clean', basefile + '.clean.fasta.qual')


def MiraRun(basefile):
    '''Assemble the sequences and write the menifest file'''
    basename = os.path.basename(basefile)
    manifest = open(basefile + ".manifest", 'w')
    manifest.write("project = " + basename + "\n")
    manifest.write(config.get('Mira Parameters', 'mirajob') + "\n")
    manifest.write(config.get('Mira Parameters', 'miracommon') + " -GE:not="
                   + config.get('Variables', 'seqcores') + " \\\n")
    manifest.write(config.get('Mira Parameters', 'mira454') + "\n\n")
    manifest.write(config.get('Mira Parameters', 'mirareadgroup') + "\n")
    manifest.write(config.get('Mira Parameters', 'miratech') + "\n")
    manifest.write("data = " + basename + ".clean.fasta\n")
    manifest.close()

    # Run mira
    cli = [config.get('Program paths', 'mira_path'), basefile + ".manifest"]

    print("\nRunning Mira using the following command:")
    print(' '.join(cli))
    RunProgram(cli, 0)

    # Convert the MAF output to SAM output
    cli = [config.get('Program paths', 'mira_path') + "convert", "-f", "maf",
           "-t", "sam", basefile + '_assembly/' + miraproject + '_d_results/' +
           miraproject + '_out.maf', basefile + ".sam"]

    print("\nConverting MAF to SAM using miraconvert:")
    print(' '.join(cli))
    RunProgram(cli, 0)


def DiscoveryTCS(basefile):
    '''Discovers SNPs in the TCS output file of Mira. Use only if trying to
       find SNPs. Output in TCS format.'''
    os.chdir(os.path.split(basefile)[0])
    print("\nRunning SNP Discovery tool module...")
    SAM_to_BAM.RunModule(basefile + '.sam',
                         basefile + '.bam')
    BAM_to_TCS.RunModule(basefile + '.bam', basefile + '_assembly/' +
                         miraproject + '_d_results/' + miraproject +
                         '_out.padded.fasta')
    TCS.RunModule(basefile + '.tcs', basefile + '_out.short.tcs',
                  int(config.get('Variables', 'minqual')),
                  int(config.get('Variables', 'mincov')))


def SNPgrabber(basefile):
    '''Grabs suitable SNPs in the short TCS output DiscoveryTCS and outputs a
       fasta with only the relevant contigs, tagged with SNP info.'''
    os.chdir(os.path.split(basefile)[0])
    print("\nRunning SNP Grabber tool module...")
    SNPg.RunModule(basefile + '_out.short.tcs',
                   basefile + '_assembly/' + miraproject + '_d_results/'
                   + miraproject + '_out.unpadded.fasta',
                   basefile + '.SNPs.fasta',
                   int(config.get('Variables', 'minqual')))


def ORFliner(basefile):
    '''This will run EMBOSS 'getorf' and use 2 scripts to filter the results
       and write a report. The paramters for 'getorf' are changed here.'''
    os.chdir(os.path.split(basefile)[0])
    cli = [config.get('Program paths', 'GetORF_path'), '-sequence',
           basefile + '.SNPs.fasta', '-outseq', basefile + '.allORFs.fasta',
           '-find', '3']
    print("\nRunning EMBOSS 'getorf' using the following command:")
    print(' '.join(cli))
    RunProgram(cli, 0)
    # After this we go to ORFmaker.py:
    print("\nRunning ORFmaker module...")
    ORFmaker.RunModule(basefile + '.allORFs.fasta')
    # Next we BLAST the resulting ORFs against the local 'nr' database:
    if config.get('Program paths', 'BLAST_path').endswith('blast2'):
        cli = [config.get('Program paths', 'BLAST_path'), '-p', 'blastx', '-d',
               config.get('Program paths', 'BLASTdb_path'), '-i',
               basefile + '.BestORF.fasta', '-H', 'T', '-a',
               config.get('Variables', 'seqcores'),
               '-o', basefile + '.ORFblast.html']
    else:
        cli = [config.get('Program paths', 'BLAST_path'), '-db',
               config.get('Program paths', 'BLASTdb_path'), '-query',
               basefile + '.BestORF.fasta', '-html', '-num_threads',
               config.get('Variables', 'seqcores'), '-out',
               basefile + '.ORFblast.html']
    print("\nRunning NCBI 'blastx' using the following command:")
    print(' '.join(cli))
    RunProgram(cli, 0)
    # Then we write the metrics report:
    print("\nRunning the metrics calculator module...")
    seqclean_log_path = "%s/seqcl_%s.fasta.log" % (os.path.split(basefile)[0],
                                                   miraproject)
    Metrics.Run_module(seqclean_log_path, basefile + '.fasta',
                       basefile + '.clean.fasta', basefile + '.fasta.qual',
                       basefile + '.clean.fasta.qual',
                       basefile + '_assembly/' + miraproject + '_d_info/'
                       + miraproject + '_info_assembly.txt', basefile
                       + '.SNPs.fasta', basefile + '.BestORF.fasta',
                       basefile + '.Metrics.html')
    # Finally we write down our report using the data gathered so far:
    print("\nRunning Reporter module...")
    Reporter.RunModule(basefile + '.BestORF.fasta', basefile + '.SNPs.fasta',
                       basefile + '.ORFblast.html', basefile + '.Report.html',
                       basefile + '_out.short.tcs')


def B2G(basefile):
    '''This will make all necessary runs to get a B2go anottation ready for the
       GUI aplication. Bummer... We start by blasting all the contigs with SNPs
       against the NCBI's 'nr'.'''
    os.chdir(os.path.split(basefile)[0])
    if config.get('Program paths', 'BLAST_path').endswith('blast2'):
        cli = [config.get('Program paths', 'BLAST_path'), '-p', 'blastx', '-d',
               config.get('Program paths', 'BLASTdb_path'), '-i',
               basefile + '.SNPs.fasta', '-m', '7', '-a',
               config.get('Variables', 'seqcores'),
               '-o', basefile + '.shortlistblast.xml']
    else:
        cli = [config.get('Program paths', 'BLAST_path'), '-db',
               config.get('Program paths', 'BLASTdb_path'), '-query',
               basefile + '.SNPs.fasta', '-outfmt', '5', '-num_threads',
               config.get('Variables', 'seqcores'), '-out',
               basefile + '.shortlistblast.xml']
    print("\nRunning NCBI 'blastx' using the following command:")
    print(' '.join(cli))
    RunProgram(cli, 0)
    # After 'blasting' we run b2g4pipe:
    if os.path.isfile(config.get('Program paths', 'Blast2go_path')):
        cli = ['java', '-jar', config.get('Program paths', 'Blast2go_path'),
               '-in', basefile + '.shortlistblast.xml', '-prop',
               os.path.split(config.get('Program paths', 'Blast2go_path'))[0]
               + '/b2gPipe.properties', '-out', basefile + '.b2g', '-a']
        print("\nRunning b2g4pipe using the following command:")
        print(' '.join(cli))
        RunProgram(cli, 0)
    else:
        quit("\nERROR:Program not found... exiting. Check your \
             configuration file.\n")


def SSRfinder(basefile):
    '''Runs the SSR finder in batch mode and generates an HTML. It's mostly
    disk I/O stress and not CPU intensive:'''
    print("\nRunning SSR finder module...")
    ssr.RunModule(basefile + '_assembly/' + miraproject + '_d_results/'
                  + miraproject + '_out.unpadded.fasta', basefile
                  + '_assembly/' + miraproject + '_d_results/' + miraproject
                  + '_out.unpadded.fasta.qual', basefile
                  + '.SSR.html', config.get('Program paths', 'Etandem_path'),
                  config.get('Variables', 'min_ssr_qual'))


def TidyUP(basefile):
    '''Tidy up the report folder:'''
    os.chdir(os.path.split(basefile)[0])
    try:
        os.mkdir('Report')
    except:
        print('Directory tree already exists - beware!')
    try:
        os.rename(basefile + '.SSR.html', 'Report/SSRs.html')
    except:
        print(basefile + '.SSR.html does not exist')
    try:
        os.rename('html_files', 'Report/html_files')
    except:
        print(basefile + 'html_files directory does not exist')
    try:
        os.rename(basefile + '.ORFblast.html', 'Report/html_files/\
                  ORFblast.html')
    except:
        print(basefile + '.ORFblast.html does not exist')
    try:
        os.rename(basefile + '.Report.html', 'Report/SNPs.html')
    except:
        print(basefile + '.Report.html does not exist')
    try:
        os.rename(basefile + '.b2g.annot', 'Report/B2g.annot')
    except:
        print(basefile + '.b2g.annot does not exist')
    try:
        shutil.copy(basefile + '.SNPs.fasta', 'Report/B2g.fasta')
    except:
        print(basefile + '.SNPs.fasta does not exist.')
    try:
        os.rename(basefile + '.Metrics.html', 'Report/Metrics.html')
    except:
        print(basefile + '.Metrics.html does not exist')
    shutil.copy(config.get('Program paths', 'Templates_path') +
                '/Report.html', 'Report/Report.html')
    # 7zip it
    cli = [config.get('Program paths', '7z_path'), 'a', '-y', '-bd', basefile
           + '.report.7z', 'Report']
    print("\n7ziping the Report folder using the following command:")
    print(' '.join(cli))
    RunProgram(cli, 0)


def RunMe(arguments):
    '''Function to parse which parts of 4Pipe4 will run.'''
    for option, number in zip(list(arguments), range(len(arguments))):
        if option == "1":
            SffExtraction(sff, basefile)
        if option == "2":
            SeqClean(basefile)
        if option == "3":
            MiraRun(basefile)
        if option == "4":
            DiscoveryTCS(basefile)
        if option == "5":
            SNPgrabber(basefile)
        if option == "6":
            ORFliner(basefile)
        if option == "7":
            B2G(basefile)
        if option == "8":
            SSRfinder(basefile)
        if option == "9":
            TidyUP(basefile)
    print("\nPipeline finished.\n")


basefile, sff, config = StartUp()
miraproject = SysPrep(basefile)
RunMe(arg.run_list)
