#! /usr/bin/env python

import os
import sys
import unittest
import itertools
import re
import subprocess
import random
import string
from cStringIO import StringIO

import sate
from sate import get_logger
from sate.test import TESTS_DIR
from sate.filemgr import TempFS
from sate.mainsate import sate_main

_LOG = get_logger(__name__)

class SateTestCase(unittest.TestCase):

    def set_up(self):
        self.ts = TempFS()
        self.ts.create_top_level_temp(prefix='runSateTest',
                parent=TESTS_DIR)
        self.job_name = 'satejob' + self.random_id(8)

    def tear_down(self):
        self.register_files()
        self.ts.remove_dir(self.ts.top_level_temp)

    def _main_execution(self, args, stdout=None, stderr=None, rc=0):
        try:
            cmd = "import sys; from sate.mainsate import sate_main; sate_main(%s)[0] or sys.exit(1)" % repr(args)
            invoc = [sys.executable, '-c', cmd]
            _LOG.debug("Command:\n\tpython -c " + repr(cmd))
            p = subprocess.Popen(invoc,
                                 stderr=subprocess.PIPE,
                                 stdout=subprocess.PIPE)
            (o, e) = p.communicate()
            r = p.wait()
            if r != rc:
                _LOG.error("exit code (%s) did not match %s" % (r,
                        rc))
                _LOG.error("here is the stdout:\n%s" % o)
                _LOG.error("here is the stderr:\n%s" % e)
            self.assertEquals(r, rc)
            if stderr is not None:
                self.assertEquals(e, stderr)
            if stdout is not None:
                self.assertEquals(o, stdout)
        except Exception, v:
            #self.assertEquals(str(v), 5)
            raise

    def _exe_run_sate(self, args, stdout=None, stderr=None, rc=0):
        script_path = os.path.join(sate.sate_home_dir(), 'run_sate.py')
        if isinstance(args, str):
            arg_list = args.split()
        else:
            arg_list = args
        cmd = ['python', script_path] + arg_list
        _LOG.debug("Command:\n\t" + " ".join(cmd))
        p = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        o, e = p.communicate()
        exit_code = p.wait()
        if exit_code != rc:
            _LOG.error("exit code (%s) did not match %s" % (exit_code,
                    rc))
            _LOG.error("here is the stdout:\n%s" % o)
            _LOG.error("here is the stderr:\n%s" % e)
        self.assertEquals(exit_code, rc)
        if stdout != None:
            self.assertEquals(o, stdout)
        if stderr != None:
            self.assertEquals(e, stderr)

    def _exe(self, args):
        sate_main(args)

    def parse_fasta_file(self, file):
        if isinstance(file, str):
            file_stream = open(file, 'rU')
        else:
            file_stream = file
        line_iter = iter(file_stream)
        data = {}
        seq = StringIO()
        name = None
        for i, line in enumerate(line_iter):
            l = line.strip()
            if l.startswith('>'):
                if name:
                    data[name] = seq.getvalue().upper()
                name = l[1:]
                seq = StringIO()
            else:
                seq.write(l)
        if name:
            data[name] = seq.getvalue().upper()
        file_stream.close()
        return data

    def parseSequenceArg(self, seq_arg):
        if isinstance(seq_arg, dict):
            return seq_arg
        else:
            return self.parse_fasta_file(seq_arg)

    def remove_gaps(self, sequence_dict):
        sd = self.parseSequenceArg(sequence_dict)
        new_sd = {}
        for name, seq in sd.iteritems():
            new_seq = re.sub(r'[-?]', '', seq)
            if new_seq != '':
                new_sd[name] = new_seq
        return new_sd

    def concatenate_sequences(self, seq_data_list):
        taxa = set()
        data_sets = []
        for f in seq_data_list:
            seqs = self.parseSequenceArg(f)
            taxa.update(seqs.keys())
            data_sets.append(seqs)
        data = {}
        for t in taxa:
            data[t] = ''
        for ds in data_sets:
            for name in taxa:
                data[name] += ds.get(name, '')
        return data

    def assertSameTaxa(self, seq_data_list):
        if len(seq_data_list) < 2:
            return
        seqs1 = self.parseSequenceArg(seq_data_list[0])
        for i in range(1, len(seq_data_list)):
            seqs2 = self.parseSequenceArg(seq_data_list[i])
            self.assertEqual(sorted(seqs1.keys()), 
                             sorted(seqs2.keys()))

    def assertSameSequences(self, seq_data_list):
        seqs1 = self.parseSequenceArg(seq_data_list[0])
        sd1 = self.remove_gaps(seqs1)
        for i in range(1, len(seq_data_list)):
            seqs2 = self.parseSequenceArg(seq_data_list[i])
            sd2 = self.remove_gaps(seqs2)
            self.assertEqual(sorted(sd1.values()), 
                             sorted(sd2.values()))

    def assertSameDataSet(self, seq_data_list):
        seqs1 = self.parseSequenceArg(seq_data_list[0])
        sd1 = self.remove_gaps(seqs1)
        for i in range(1, len(seq_data_list)):
            seqs2 = self.parseSequenceArg(seq_data_list[i])
            sd2 = self.remove_gaps(seqs2)
            self.assertSameTaxa([sd1, sd2])
            self.assertSameSequences([sd1, sd2])
            for name, seq in sd1.iteritems():
                self.assertEqual(seq, sd2[name])

    def assertSameInputOutputSequenceData(self, 
            seq_data_list1, seq_data_list2):
        for i in range(len(seq_data_list1)):
            _LOG.debug("comparing %s to %s" % (seq_data_list1[i],
                    seq_data_list2[i]))
            seqs1 = self.parseSequenceArg(seq_data_list1[i])
            seqs2 = self.parseSequenceArg(seq_data_list2[i])
            self.assertSameDataSet([seqs1, seqs2])

    def assertSameConcatenatedSequences(self, 
            concatenated_data, seq_data_list):
        concat_in = self.concatenate_sequences(sorted(seq_data_list))
        concat_out = self.parseSequenceArg(concatenated_data)
        sd_in = self.remove_gaps(concat_in)
        sd_out = self.remove_gaps(concat_out)
        self.assertSameSequences([sd_in, sd_out])

    def assertNoGapColumns(self, seq_data_list):
        for seq_data in seq_data_list:
            sd = self.parseSequenceArg(seq_data)
            columns_to_taxa = {}
            for name, seq in sd.iteritems():
                for column_index, residue in enumerate(seq):
                    if residue == '-':
                        if column_index not in columns_to_taxa.keys():
                            columns_to_taxa[column_index] = [name]
                        else:
                            columns_to_taxa[column_index].append(name)
            self.assertEqual(len(columns_to_taxa.keys()), len(set(columns_to_taxa.keys())))
            for col, name_list in columns_to_taxa.iteritems():
                self.assertEqual(len(name_list), len(set(name_list)))
                self.assertNotEqual(len(name_list), len(sd.keys()))

    def random_id(self, length=8,
            char_pool=string.ascii_letters + string.digits):
        return ''.join(random.choice(char_pool) for i in range(length))

    def register_files(self):
        self.ts._register_created_dir(os.path.join(
                self.ts.top_level_temp, self.job_name))
        for path, dirs, files in os.walk(self.ts.top_level_temp):
            for f in files:
                if f.startswith(self.job_name):
                    self.ts.run_generated_filenames.append(
                            os.path.join(path, f))
            for d in dirs:
                if d.startswith(self.job_name):
                    self.ts._register_created_dir(d)

