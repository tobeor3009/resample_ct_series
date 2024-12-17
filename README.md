
---

# 3D CT Resample

This repository provides a ct resampling code and example code (except data):  
You can choose either SimpleITK or scipy's zoom to perform resampling.

<p align="center">
  <img src="resample_visualize.png" alt="Image Patch Example" width="90%">
</p>

<p align="center">
  <b>Figure 3:</b> Positive Image Patch (left), Mask Patch (center), Tissue Patch (right).
</p>

1. **Extracting and Organizing Axial Series from Mixed Series Data**  
   Refer to the notebook: `0_Extract_Axial_Series.ipynb`  
   In real-world datasets, Axial, Sagittal, and Coronal images, or even Scout images, may be mixed together.  
   Here is an example of a script that extracts and organizes Axial images when such data is stored in a single folder.  

2. **Resample 3D CT**  
   Here is an example of code for resampling a CT series.  
   Refer to the notebook: `1_Resample_CT_Series.ipynb`

### Usage
   The steps for resampling are as follows:
   **Step 1**: Use `utils.resize_dicom_series` to resample the **SimpleITK image** and obtain the **resampled sitk_image object**.
   **Step 2**: Use `utils.write_series_to_path` to write **SimpleITK image(3D CT Series)** to target folder.

   For more details, refer to the docstrings of `utils.resize_dicom_series` and `utils.write_series_to_path`. 

### Future Work

We are currently preparing a research paper on **CT-Super-Resolution** based on the methods demonstrated in this repository.

### Contact

If you have any questions or suggestions, feel free to reach out via:  
📧 **Email**: tobeor3009@gmail.com  
💬 **GitHub Issues**

--- 

Let me know if you need further refinements! 😊