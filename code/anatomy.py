from nipype.interfaces import spm
from nipype.interfaces import matlab
from nipype.interfaces import cat12
from nipype.interfaces.freesurfer import ApplyVolTransform, ApplyMask
import nipype.pipeline.engine as pe
import nibabel as nib
import numpy as np
import os
import sys
import gzip
import shutil
import subprocess
from tempfile import TemporaryDirectory

#

matlab_cmd = '/opt/spm12/run_spm12.sh /opt/mcr/v93 script'
spm_path = '/opt/spm12/spm12_mcr/home/gaser/gaser/spm/spm12'
spm.SPMCommand.set_mlab_paths(matlab_cmd=matlab_cmd, use_mcr=True)

def set_spm_path(new_spm_path):
    global spm_path
    spm_path = new_spm_path
    matlab.MatlabCommand.set_default_paths(spm_path)

def check_spm_path():
    print(spm_path)
    
def load_niimg(niimg):
    if type(niimg) is str:
        return nib.load(niimg)
    else:
        return niimg

def normalize(niimg_in,out_file=None):
    niimg_in = load_niimg(niimg_in)
    data = niimg_in.get_fdata()
    data_norm = (data-np.min(data))/(np.max(data)-np.min(data))
    niimg_out = nib.Nifti1Image(data_norm,niimg_in.affine,niimg_in.header)
    if out_file:
        nib.save(niimg_out,out_file)
    return niimg_out

def multiply(niimg_in1, niimg_in2, out_file=None):
    niimg_in1 = load_niimg(niimg_in1)
    niimg_in2 = load_niimg(niimg_in2)
    data1 = niimg_in1.get_fdata()
    data2 = niimg_in2.get_fdata()
    data_mult = data1 * data2
    niimg_out = nib.Nifti1Image(data_mult,niimg_in1.affine,niimg_in1.header)
    if out_file:
        nib.save(niimg_out,out_file)
    return niimg_out

def mprageize(inv2_file, uni_file, out_file=None):
    """ 
    Based on Sri Kashyap (https://github.com/srikash/presurfer/blob/main/func/presurf_MPRAGEise.m)
    """
    
    # mprageize using temporary directory
    with TemporaryDirectory() as tmpdirname:
        copied_inv2 = os.path.join(tmpdirname, 'copied_inv2.nii')
        copied_uni = os.path.join(tmpdirname, 'copied_uni.nii')
        shutil.copyfile(inv2_file, copied_inv2)
        shutil.copyfile(uni_file, copied_uni)

        # bias correct INV2
        seg = spm.NewSegment()
        seg.inputs.channel_files = copied_inv2
        seg.inputs.channel_info = (0.001, 30, (False, True))
        tissue1 = ((os.path.join(spm_path,'tpm','TPM.nii'), 1), 2, (False,False), (False, False))
        tissue2 = ((os.path.join(spm_path,'tpm','TPM.nii'), 2), 2, (False,False), (False, False))
        tissue3 = ((os.path.join(spm_path,'tpm','TPM.nii'), 3), 2, (False,False), (False, False))
        tissue4 = ((os.path.join(spm_path,'tpm','TPM.nii'), 4), 3, (False,False), (False, False))
        tissue5 = ((os.path.join(spm_path,'tpm','TPM.nii'), 5), 4, (False,False), (False, False))
        tissue6 = ((os.path.join(spm_path,'tpm','TPM.nii'), 6), 2, (False,False), (False, False))
        seg.inputs.tissues = [tissue1, tissue2, tissue3, tissue4, tissue5, tissue6]    
        seg.inputs.affine_regularization = 'mni'
        seg.inputs.sampling_distance = 3
        seg.inputs.warping_regularization = [0, 0.001, 0.5, 0.05, 0.2]
        seg.inputs.write_deformation_fields = [False, False]
        seg_results = seg.run(cwd = os.path.dirname(os.path.abspath(out_file)))
        
        # normalize bias corrected INV2
        norm_inv2_niimg = normalize(seg_results.outputs.bias_corrected_images)
                                
        # multiply normalized bias corrected INV2 with UNI
        uni_mprageized_niimg = multiply(norm_inv2_niimg,copied_uni)

        # Load the output path and then save it to the destination folder
        nib.save(uni_mprageized_niimg, out_file)

def cat12_seg(in_file,cat12_output_dir):

    # CAT12 segmentation using temporary memory
    with TemporaryDirectory() as tmpdirname:
        copied_input = os.path.join(tmpdirname, os.path.basename(in_file))
        shutil.copyfile(in_file, copied_input)
    
        # Load the bias corrected image 
        img = nib.load(copied_input)

        # Calculate median of resolution - to be used by CAT12 object
        median_res = np.median(img.header.get_zooms()[:3])
        
        # Create CAT12 object with specific parameters
        cat12_segment = cat12.CAT12Segment(in_files = copied_input)
        cat12_segment.inputs.internal_resampling_process = (median_res, 0.1)
        cat12_segment.inputs.surface_and_thickness_estimation = 0
        cat12_segment.inputs.surface_measures = 0
        cat12_segment.inputs.neuromorphometrics = False
        cat12_segment.inputs.lpba40 = False
        cat12_segment.inputs.cobra = False
        cat12_segment.inputs.hammers = False
        cat12_segment.inputs.gm_output_native = True    
        cat12_segment.inputs.gm_output_modulated = False
        cat12_segment.inputs.gm_output_dartel = False
        cat12_segment.inputs.wm_output_native = True    
        cat12_segment.inputs.wm_output_modulated = False
        cat12_segment.inputs.wm_output_dartel = False
        cat12_segment.inputs.csf_output_native = True    
        cat12_segment.inputs.csf_output_modulated = False
        cat12_segment.inputs.csf_output_dartel = False
        cat12_segment.inputs.jacobianwarped = False
        cat12_segment.inputs.label_warped = False
        cat12_segment.inputs.las_warped = False
        cat12_segment.inputs.save_bias_corrected = False
        cat12_segment.inputs.warps = (0, 0)
        cat12_segment.inputs.output_labelnative = True
        # cat12_segment.inputs.output_surface = False
        # cat12_segment.inputs.no_surf = True
        cat12_segment.run(cwd = tmpdirname) 

        # Get current filename of the bias Corrected file
        in_file_basename = os.path.basename(os.path.abspath(in_file))
        
        # Create output directory if it does not exist
        if not os.path.exists(cat12_output_dir):
             os.makedirs(cat12_output_dir)

        # Copy data out of tmp
        shutil.copy(os.path.join(tmpdirname, 'mri', 'p1' + in_file_basename), os.path.join(cat12_output_dir, 'p1' + in_file_basename))
        shutil.copy(os.path.join(tmpdirname, 'mri', 'p2' + in_file_basename), os.path.join(cat12_output_dir, 'p2' + in_file_basename))

        # load the path of output GM and WM files from the "mri" folder into variables
        gm_file = os.path.join(cat12_output_dir, 'p1' + in_file_basename)
        wm_file = os.path.join(cat12_output_dir, 'p2' + in_file_basename)

        return gm_file, wm_file

def mp2rage_recon_all(inv2_file,uni_file,output_fs_dir=None, gdc_coeff_file=None):
    
    #get codedir
    codeDir=os.getcwd()

    # Get current working directory and filename of the loaded MPRAGE file
    cwd = os.path.dirname(os.path.abspath(inv2_file))
    inv2_basename = str(os.path.basename(os.path.abspath(inv2_file)))
    uni_basename=str(os.path.basename(os.path.abspath(uni_file)))

    # Navigation through folders to get the path of derivatives folder where output is saved
    subject_path = os.path.dirname(os.path.dirname(cwd))
    subject_foldername = os.path.basename(subject_path)
    orient_dep_path = os.path.dirname(os.path.dirname(os.path.dirname(cwd)))
    if gdc_coeff_file is not None:
        derivatives_path = os.path.join(orient_dep_path, 'derivatives/mprage_gdc_recon-all', subject_foldername)
    else:
        derivatives_path = os.path.join(orient_dep_path, 'derivatives/mprage_recon-all', subject_foldername)

    # Check if the output directory exists - if not create it
    if not os.path.exists(derivatives_path):
        os.makedirs(derivatives_path)
        print(f"****** created directory: {derivatives_path}")
    else:
        print(f"****** directory already exists: {derivatives_path}")
    
    # Create filename and path for output
    uni_mprageized_file = os.path.join(derivatives_path, 'T1w.nii')
    uni_mprageized_brain_file =   os.path.join(derivatives_path,'T1w_brain.nii') 
    brainmask_file =  os.path.join(derivatives_path, 'T1w_brainmask.nii')

    # Perform bias correction by calling the function
    mprageize(inv2_file,uni_file,uni_mprageized_file)
    print("****** mprageize  complete")

    #run gdc
    if gdc_coeff_file is not None:
        print("****** running gdc")
        subprocess.run([os.path.join(codeDir, 'run_gdc.sh'), uni_mprageized_file,  gdc_coeff_file])
        uni_mprageized_file = uni_mprageized_file.replace('T1w','T1w_gdc')
        uni_mprageized_brain_file =  uni_mprageized_brain_file.replace('T1w_brain','T1w_brain_gdc')
        brainmask_file = brainmask_file.replace('brainmask','brainmask_gdc')
    print("****** gdc complete")

    ## Obtain GM, WM, Brainmask and Brain extraction using cat12 ##    
    # Call CAT12 function on bias corrected image
    cat12_output_dir=os.path.join(derivatives_path,'mri')
    gm_file, wm_file = cat12_seg(uni_mprageized_file,cat12_output_dir)
    print("****** CAT12 complete")

    # Load the GM and WM files (saved by CAT12) and mprageized file
    gm_nii = nib.load(gm_file)
    wm_nii = nib.load(wm_file)
    uni_mprageized_nii = nib.load(uni_mprageized_file)
    print("****** segmentations and uni_mprageized_loaded")

    # Get data from these nifit files
    gm_data = gm_nii.get_fdata()
    wm_data = wm_nii.get_fdata()
    uni_mprageized_data = uni_mprageized_nii.get_fdata()    
    print("****** data from segmentations and uni_mprageized_data extracted")

    # Creating and saving brain mask
    brainmask_data = np.array(((wm_data > 0) | (gm_data > 0)),dtype=int)
    brainmask_nii = nib.Nifti1Image(brainmask_data,
                                    uni_mprageized_nii.affine,
                                    uni_mprageized_nii.header)
    nib.save(brainmask_nii, brainmask_file)
    print("****** brain mask saved")

    # Creating and saving brain extraction
    uni_mprageized_brain_data = brainmask_data * uni_mprageized_data
    uni_mprageized_brain_nii = nib.Nifti1Image(uni_mprageized_brain_data,
                                               uni_mprageized_nii.affine,
                                               uni_mprageized_nii.header)
    nib.save(uni_mprageized_brain_nii,uni_mprageized_brain_file)
    print("****** brain extraction saved")

    ##########################################
    ##### run recon-all from Freesurfer ######
    #########################################

    # define directory for Freeseurfer
    fs_dir = derivatives_path
    sub = 'freesurfer'
        
    # autorecon1 without skullstrip removal (~11 mins)
    os.system("recon-all" + \
          " -i " + uni_mprageized_file + \
          " -hires" + \
          " -autorecon1" + \
          " -noskullstrip" + \
          " -sd " + fs_dir + \
          " -s " + sub + \
          " -parallel")
    print("****** auto recon 1 is complete")

    # apply brain mask from CAT12
    transmask = ApplyVolTransform()
    transmask.inputs.source_file = brainmask_file
    transmask.inputs.target_file = os.path.join(fs_dir, sub, 'mri', 'orig.mgz')
    transmask.inputs.reg_header = True
    transmask.inputs.interp = "nearest"
    transmask.inputs.transformed_file = os.path.join(fs_dir, sub, 'mri', 'brainmask_mask.mgz')
    transmask.inputs.args = "--no-save-reg"
    transmask.run(cwd=derivatives_path)
    print("****** applying brain mask from CAT12 is complete")

    applymask = ApplyMask()
    applymask.inputs.in_file = os.path.join(fs_dir, sub,'mri','T1.mgz')
    applymask.inputs.mask_file = os.path.join(fs_dir, sub, 'mri', 'brainmask_mask.mgz')
    applymask.inputs.out_file =  os.path.join(fs_dir, sub, 'mri', 'brainmask.mgz')
    applymask.run(cwd=derivatives_path)
    print("****** apply mask is complete")

    shutil.copy2(os.path.join(fs_dir, sub, 'mri', 'brainmask.mgz'),
                 os.path.join(fs_dir, sub, 'mri','brainmask.auto.mgz'))

    # continue recon-all
    with open(os.path.join(derivatives_path,'expert.opts'), 'w') as text_file:
        text_file.write('mris_inflate -n 100\n')
        print("****** expert option saved as text file")
    
     # autorecon2 and 3
    autorecon23_call = "recon-all" + \
                     " -hires" + \
                     " -autorecon2" + " -autorecon3"\
                     " -sd " + fs_dir + \
                     " -s " + sub + \
                     " -expert " + os.path.join(derivatives_path,'expert.opts') + \
                     " -xopts-overwrite" + \
                     " -parallel "
                    
    # deal with freesurfer version 7.3.2 bug:
    fs_version = subprocess.check_output(['recon-all', '--version']).decode('utf-8').split()[0]
    if '7.3.2' in fs_version:
        autorecon23_call = autorecon23_call + " -careg"

    os.system(autorecon23_call)
