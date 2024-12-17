import pydicom
import SimpleITK as sitk
import numpy as np
import os
import time
from scipy.ndimage import zoom
from pydicom.uid import generate_uid
import json
import os

resize_method_list = ["sitk", "scipy"]

def read_json_as_dict(json_path):
    json_file = open(json_path, encoding="utf-8")
    json_str = json_file.read()
    json_dict = json.loads(json_str)
    return json_dict

def get_z_position(dicom_file):
    dicom_position = dicom_file[pydicom.tag.Tag((0x0020, 0x0032))].value
    dicom_z_position = float(dicom_position[-1])
    return dicom_z_position

def get_slice_thickness(dcm_path_list):
    dcm_obj = pydicom.dcmread(dcm_path_list[0], force=True)
    return dcm_obj["SliceThickness"].value

def read_dcm_path_list_as_sitk(dense_dcm_path_list):
    reader = sitk.ImageSeriesReader()
    reader.SetFileNames(dense_dcm_path_list)
    reader.MetaDataDictionaryArrayUpdateOn()
    reader.LoadPrivateTagsOn()
    image = reader.Execute()
    return image, reader

def resize_dicom_series_scipy(image, resize_factor_list, is_label=False): #resize_factor_list는 각차원에 대해 리사이즈할 비율
    resize_factor_list = list(resize_factor_list)
    image_array = sitk.GetArrayFromImage(image)
    resample_array = zoom(image_array, resize_factor_list[::-1], order=3 if is_label else 0)
    dimension = image.GetDimension()
    reference_physical_size = np.zeros(image.GetDimension())
    reference_physical_size[:] = [max(sz, 1) * spc if sz * spc > mx else mx
                                  for sz, spc, mx in zip(image.GetSize(), image.GetSpacing(), reference_physical_size)]
    reference_origin = image.GetOrigin()
    reference_direction = image.GetDirection()

    reference_size = [round(sz * resize_factor) for sz, resize_factor in zip(image.GetSize(), resize_factor_list)]
    reference_spacing = [phys_sz / (max(sz, 1)) for sz, phys_sz in zip(reference_size, reference_physical_size)]
    resample_image = sitk.GetImageFromArray(resample_array)
    resample_image.SetOrigin(reference_origin)
    resample_image.SetSpacing(reference_spacing)
    resample_image.SetDirection(reference_direction)
    for key in image.GetMetaDataKeys():
        resample_image.SetMetaData(key, image.GetMetaData(key))
    return resample_image


def resize_dicom_series_sitk(sitk_image, resize_factor_list, is_label=False):
    
    # Resample images to 2mm spacing with SimpleITK
    original_spacing = sitk_image.GetSpacing()
    original_size = sitk_image.GetSize()
    out_spacing = [origin_spc / resize_factor for origin_spc, resize_factor in zip(original_spacing, resize_factor_list)]
    out_size = [
        int(np.round(original_size[0] * (original_spacing[0] / out_spacing[0]))),
        int(np.round(original_size[1] * (original_spacing[1] / out_spacing[1]))),
        int(np.round(original_size[2] * (original_spacing[2] / out_spacing[2])))]

    resample = sitk.ResampleImageFilter()
    resample.SetOutputSpacing(out_spacing)
    resample.SetSize(out_size)
    resample.SetOutputDirection(sitk_image.GetDirection())
    resample.SetOutputOrigin(sitk_image.GetOrigin())
    resample.SetTransform(sitk.Transform())
    resample.SetDefaultPixelValue(sitk_image.GetPixelIDValue())

    if is_label:
        resample.SetInterpolator(sitk.sitkNearestNeighbor)
    else:
        resample.SetInterpolator(sitk.sitkBSpline)

    return resample.Execute(sitk_image)

def resize_dicom_series(image, resize_factor_list, is_label=False, resize_method="sitk"):
    """
    Resize a DICOM series using scipy's zoom function or sitk resampling step while preserving metadata.

    This function takes a SimpleITK image object, resizes it according to the given scale factor
    for each dimension, and preserves the original metadata such as spacing, origin, and direction.
    It is designed for resizing both image data (order=3 for interpolation) and label data (order=0 for nearest neighbor).

    Parameters:
        image (sitk.Image): 
            The input SimpleITK image object (e.g., DICOM).
        resize_factor_list (list or tuple): 
            A list or tuple of scale factors for each dimension (x, y, z) in the image. 
            Each value represents the scale to resize along the corresponding axis.
        is_label (bool, optional): 
            If True, the function uses nearest neighbor interpolation (order=0) suitable for label maps.
            If False, cubic interpolation (order=3) is used for image data.
            Default is False.

    Returns:
        sitk.Image:
            A resized SimpleITK image object with updated spacing and preserved metadata.

    Example:
        >>> import SimpleITK as sitk
        >>> from glob import glob
        >>> from natsort import natsorted
        # Load an example DICOM series
        
        >>> dicom_series_folder = "path/to/dicom_series_folder"
        >>> dicom_path_list = natsort(glob(dicom_series_folder))
        >>> source_image, source_reader = read_dcm_path_list_as_sitk(dicom_path_list)

        # Define resize factors (e.g., 0.5 in z, y, x dimensions)
        # it resample image as shape (512, 512, 128) => (256, 256, 64)
        >>> resize_factors = [0.5, 0.5, 0.5]

        # Resize the image
        >>> resized_image = resize_dicom_series(image, resize_factors, is_label=False, resize_method="sitk")
        
        # Save the resized image
        >>> write_series_to_path(reader=source_reader,
                                 target_image=resized_image, 
                                 original_sample_path=dicom_path_list[0], 
                                 target_path="path/to/save_resampled_folder", 
                                 slice_thickness=None,
                                 inverse_instance_num=False)

    Notes:
        - The function calculates new spacing and dimensions to match the resized image.
        - Metadata such as origin, spacing, and direction are preserved.
        - Use `is_label=True` for segmentation masks to avoid interpolation artifacts.
    """    
    assert resize_method in resize_method_list, f"supported resize_method_list is {resize_method_list}"
    
    if resize_method == "sitk":
        resample_image = resize_dicom_series_sitk(image, resize_factor_list, is_label)
    elif resize_method == "scipy":
        resample_image = resize_dicom_series_scipy(image, resize_factor_list, is_label)
    resample_image = sitk.Cast(resample_image, sitk.sitkInt16)
    return resample_image

def write_series_to_path(reader, target_image, original_sample_path, target_path, inverse_instance_num=True, slice_thickness=None):
    """
    The resized Sitk Image Object (3D CT) is written after extracting metadata from the given sitk_reader and the original DICOM path.    

    Parameters:
        reader (sitk.Image): 
            The reader used at read soucre_image.
        target_image (sitk.Image):
            The resampled image.
        original_sample_path (str):
            first dicom path in original dicom_path_list
        target_path (str):
            ct series folder path you want to save.
        inverse_instance_num (bool):
            If it is True, you will match 0001.dcm to Instance Number 1.
            If it is False, you will match 0001.dcm to the last Instance Number.
        slice_thickness (str or float)
            If this value is provided, it will overwrite the SliceThickness flag.
            
    Notes:
        - for detail usage, refer resize_dicom_series function docstring
    """        
    
    tags_to_copy = ["0010|0010", # Patient Name
                    "0010|0020", # Patient ID
                    "0010|0030", # Patient Birth Date
                    "0020|000D", # Study Instance UID, for machine consumption
                    "0020|0010", # Study ID, for human consumption
                    "0008|0020", # Study Date
                    "0008|0030", # Study Time
                    "0008|0050", # Accession Number
                    "0008|0060"  # Modality
    ]

    modification_time = time.strftime("%H%M%S")
    modification_date = time.strftime("%Y%m%d")
    direction = target_image.GetDirection()
    
    series_tag_value = reader.GetMetaData(0,"0008|103e")
#     try:
#         series_tag_value = reader.GetMetaData(0,"0008|103e")
#     except RuntimeError:
#         series_tag_value = "tag_None"
#     print(series_tag_value)
    original_image = sitk.ReadImage(original_sample_path)
    original_key_tuple = original_image.GetMetaDataKeys()
    original_tag_values = [(tag, original_image.GetMetaData(tag)) for tag in original_key_tuple]
    series_tag_values = [(k, original_image.GetMetaData(k)) for k in tags_to_copy if original_image.HasMetaDataKey(k)] + \
                     [("0008|0031",modification_time), # Series Time
                      ("0008|0021",modification_date), # Series Date
                      #("0008|0008","DERIVED\\SECONDARY"), # Image Type
                      #("0020|000e", "1.2.826.0.1.3680043.2.1125."+modification_date+".1"+modification_time), # Series Instance UID
                      ("0020|0037", '\\'.join(map(str, (direction[0], direction[3], direction[6],# Image Orientation (Patient)
                                                        direction[1],direction[4],direction[7])))),
                      ("0008|103e", series_tag_value + " Processed-SimpleITK")]

    writer = sitk.ImageFileWriter()
    writer.KeepOriginalImageUIDOn()
    
    os.makedirs(target_path, exist_ok=True)
    target_image_depth = target_image.GetDepth()
    
    study_instance_uid = generate_uid()
    series_instance_uid = generate_uid()
    sop_uid = generate_uid()
    time_created_date = time.strftime("%Y%m%d")
    time_crateed_time = time.strftime("%H%M%S")
    for index in range(target_image_depth):
        image_slice = target_image[:, :, index]

        # Tags shared by the series.
        if inverse_instance_num:
            instance_number = target_image_depth - index
        else:
            instance_number = index + 1
            
        for tag, value in original_tag_values:
            try:
                image_slice.SetMetaData(tag, value)
            except:
                continue
        for tag, value in series_tag_values:
            image_slice.SetMetaData(tag, value)
        # Setting the type to CT preserves the slice location.
        image_slice.SetMetaData("0008|0060", "CT")  # set the type to CT so the thickness is carried over
        # Slice specific tags.
        image_slice.SetMetaData("0008|0012", time_created_date) # Instance Creation Date
        image_slice.SetMetaData("0008|0013", time_crateed_time) # Instance Creation Time
        image_slice.SetMetaData("0008|0018", sop_uid) # SOP UID
        
        image_slice.SetMetaData("0020|0032", '\\'.join(map(str, target_image.TransformIndexToPhysicalPoint((0, 0, index))))) # Image Position (Patient)
        image_slice.SetMetaData("0020|0013", str(instance_number)) # Instance Number
        if slice_thickness is not None:
            image_slice.SetMetaData("0018|0050", str(slice_thickness)) # set series slice thickness
        image_slice.SetMetaData("0020|000E", series_instance_uid)
        image_slice.SetMetaData("0020|000D", study_instance_uid)
        
        file_name = f'{target_path}/{instance_number:04d}.dcm'
        writer.SetFileName(file_name)
        writer.Execute(image_slice)