import argparse


def setup_cli():
    parser = argparse.ArgumentParser(description='Provides various commands ')
    return parser


parser = setup_cli()
args = parser.parse_args()