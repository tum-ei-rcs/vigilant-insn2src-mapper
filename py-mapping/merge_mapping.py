#!/usr/bin/python
#
# Merges mutiple files together. Could be done in pure bash, but is a python script for historical
# reasons.
#
import argparse
import os
import sys
import logging
import coloredlogs
import re


coloredlogs.install(level='DEBUG', fmt='[ %(levelname)s ] <%(name)s> %(message)s')
log = logging.getLogger()


def get_files_with_ext(ext, path):
    return [os.path.join(path, f) for f in os.listdir(path) if f.endswith(ext)]


def main(args):
    def validate_mapping_files():
        ret = list()
        p = re.compile(r'mapping_([A-Za-z0-9_]+).csv')
        for f in mapping_files:
            m = p.search(f)
            func_name = m.group(1)
            ret.append((func_name, f))

        return sorted(ret, key=lambda x: x[0])

    def merge_mapping_files():
        with open(args.out_file[0], 'w') as fp:
            for func, fpath in map_list:
                with open(fpath, 'r') as mfp:
                    fp.write(mfp.read())
                fp.write('\n\n')
        log.info("Merged mapping output saved in: {}\n".format(args.out_file[0]))

    # Get mapping csv
    mapping_files = get_files_with_ext('.csv', args.mapping_dir[0])
    map_list = validate_mapping_files()
    assert len(map_list), 'No mapping files found.'
    merge_mapping_files()


def parse_args():
    def check_dir(dpath):
        if not os.path.isdir(dpath):
            raise argparse.ArgumentTypeError('Invalid directory path given.')
        return dpath

    parser = argparse.ArgumentParser(description="Merge mapping output from (py-mapping)." + 
                                     " Input folder must contain a single source file.")

    parser.add_argument('-m', '--mapping-dir',
                        nargs=1, type=check_dir,
                        help='Directory path containing individual mapping files')
    # basically ignored: only there for backwards compatibility:
    parser.add_argument('-b', '--bench-dir', type=check_dir,
                        help='Benchmark directory path')
    parser.add_argument('-o', '--out-file',
                        nargs=1,
                        help='Output file path')

    return parser.parse_args()


if __name__ == '__main__':
    sys.exit(main(parse_args()))
