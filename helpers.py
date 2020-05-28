# Module for additional helper functions
# Author - Jakub Frejlach
# 2020

def export_labeling(freq, filepath, train_file):
    """
        Compute significancy from frequency and export is as labeling file.

        Args:
            filepath:       string with path to new file with labeling
            train_file:     path to train file to retrieve strings count
    """
    with open(train_file, 'r') as f:
        string_count = int(f.readline())
    with open(filepath, 'w') as f:
        for state, frequency in freq.items():
            significancy = frequency / string_count
            f.write('{}:{}\n'.format(state, significancy))
