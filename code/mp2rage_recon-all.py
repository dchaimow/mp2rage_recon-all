#! /usr/bin/env python3
import anatomy
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="mp2rage_recon-all: runs modified FreeSurfer recon-all pipeline on MP2RAGE data "
    )
    parser.add_argument(
        "--inv2", type=str, help="path to nifti file containing MP2RAGE INV2 data"
    )
    parser.add_argument(
        "--uni", type=str, help="path to nifti file containing MP2RAGE UNI data"
    )
    parser.add_argument("--fs_dir", type=str, help="path to output fs dir")
    parser.add_argument(
        "--gdc_coeff_file",
        help="run gradient disortion correction using specified coefficient file",
    )
    args = parser.parse_args()

    anatomy.mp2rage_recon_all(
        args.inv2,
        args.uni,
        output_fs_dir=args.fs_dir,
        gdc_coeff_file=args.gdc_coeff_file,
    )
