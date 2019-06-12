import argparse
import os
import sys
import logging
import coloredlogs
import re


coloredlogs.install(level='DEBUG', fmt='[ %(levelname)s ] <%(name)s> %(message)s')
log = logging.getLogger()


def get_files_with_ext(ext, dir):
    return [os.path.join(dir, f) for f in os.listdir(dir) if f.endswith(ext)]


def main(args):
    def validate_mapping_files(mapping_files):
        """ 
        Validates and returns a list of tuples (func_name, mapping_file_path)

        Input:
            - mapping_files : A list of mapping files
        """
        map_list = list()
        p = re.compile(r'mapping_([A-Za-z0-9_]+).csv')
        for f in mapping_files:
            m = p.search(f)
            func_name = m.group(1)
            map_list.append((func_name, f))
        return map_list

    def merge_mapping_files(map_list, source_file_name):
        with open(args.out_file[0], 'w') as fp:
            for func, fpath in map_list:
                # Write header [source_file_path, func_name]
                fp.write('[{},{}]\n'.format(source_file_name, func))

                # Write original file content
                log.info("Appending mapping information for function: {}".format(func))
                with open(fpath, 'r') as mfp:
                    fp.write(mfp.read())

                fp.write('\n\n')
        log.info("Merged mapping output saved in: {}\n".format(args.out_file[0]))

    # Get source file
    source_files = get_files_with_ext('.c', args.bench_dir[0])
    assert len(source_files) != 0, "No source file found."
    
    # Find the correct source, ignore those ending with _i.c
    source_file_name = ''
    for f in source_files:
        if f.endswith('_i.c'):
            continue
        assert source_file_name == '', 'Multiple source files found.'
        source_file_name = f
    log.info("Merging mapping files for source file: {}".format(source_file_name))        

    # Get mapping csv
    mapping_files = get_files_with_ext('.csv', args.mapping_dir[0])
    map_list = validate_mapping_files(mapping_files)
    assert len(map_list), 'No mapping files found.'
    
    # Merge mapping output
    merge_mapping_files(map_list, source_file_name)


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
    parser.add_argument('-b', '--bench-dir',
                        nargs=1, type=check_dir,
                        help='Benchmark directory path')
    parser.add_argument('-o', '--out-file',
                        nargs=1,
                        help='Output file path')

    return parser.parse_args()


if __name__ == '__main__':
    sys.exit(main(parse_args()))
