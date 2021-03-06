def extract_plates(path, sheet_list):
    """Will return a sublist of plates absorbance information in dataframe format
    Must ensure that excel sheet has only the samples made in the csv plan as will cause errors downstream."""
    plate_dfs = []
    for sheet_name in sheet_list:
        plate_df = pd.read_excel(path, sheet_name = sheet_name).T
        plate_dfs.append(plate_df)
    return plate_dfs

def merge_wavelength_dfs(df_list):
    merge_list = []
    for i, df in enumerate(df_list):
        if i == 0:
            df = df
        else: 
            df = df.drop(['Wavelength'])
        merge_list.append(df)
    return pd.concat(merge_list)

def baseline_correction(df_samples, baseline_series): 
    """Given the series iloc of a the blank, subtracts the value at every wavelength of blank at resp. wavelength. 
    Simple subtraction blanking."""
    new_df_con = []
    for key, row in df_samples.iterrows():
        if key == 'Wavelength':
            wavelengths = row
            new_df_con.append(wavelengths)
        else: 
            series = row
            corrected = series.subtract(baseline_series)
            new_df_con.append(corrected)
    
    baseline_corrected_df = pd.concat(new_df_con, axis = 1).T
    baseline_corrected_df.index = df_samples[0].index
    return baseline_corrected_df


def add_abs_to_sample_info(sample_info_df, abs_df):
    
    wavelengths = list(abs_df.loc['Wavelength'])
    wavelengths_names = [str(wavelength)+'nm' for wavelength in wavelengths]
    abs_df.columns = wavelengths_names
    
    
    sample_info_df.reset_index(drop=True, inplace=True)
    abs_df.reset_index(drop=True, inplace=True)
    combined_df = pd.concat([sample_info, abs_df], axis = 1)
    return combined_df

def remove_visual_outliers(x, y, z, z_score_threshold = 3):
    """This is not a to remove statistical outliers, only to remove values which present. Outliers will be 
    removed based on the data of z and subsequently from x and y given the same indexes of entries. Inputs must be nparrays"""

    z_array = np.asarray(z)
    z_scores = np.abs(stats.zscore(np.asarray(z)))
    threshold = z_score_threshold
    index_to_remove = np.where(z_scores > threshold)[0] # must be in ascending order
    
    x = x.copy()
    y = y.copy()
    z = z.copy()
    
    for index in reversed(index_to_remove): # reveresed to perserve index
        del x[index]
        del y[index]
        del z[index]
    
    xyz_array = [x,y,z]
    return xyz_array

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

gauth = GoogleAuth()
# gauth.LocalWebserverAuth()
gauth.LoadCredentialsFile("OT2creds.txt") 
drive = GoogleDrive(gauth)

def team_drive_dict(): # for now lets keep this static, will prompt to login for the team drive. 
    """team_drive_id must be formatted with single quotations in the string, with the string datatype coming from double 
    quotation marks i.e. "'team_drive_id'" """ 
    
    team_drive_folder_list = drive.ListFile({'q':"'0AHSxuxDy84zYUk9PVA' in parents and trashed=false", 
                                'corpora': 'teamDrive', 
                                'teamDriveId': '0AHSxuxDy84zYUk9PVA', 
                                'includeTeamDriveItems': True, 
                                'supportsTeamDrives': True}).GetList()

    team_drive_id_dict = {}    
    for file in team_drive_folder_list: # hmm the fact that this is static ID we can make into dictioanry
        team_drive_id_dict[file['title']] =  file['id']
    
    return team_drive_id_dict

def file_and_folder_navi(folder_id): # for now lets keep this static, will prompt to login for the team drive. 
    folder_id = '"' + folder_id  + '"'
    
    drive_list = drive.ListFile({'q':folder_id + " in parents and trashed=false", 
                                'corpora': 'teamDrive', 
                                'teamDriveId': '0AHSxuxDy84zYUk9PVA', 
                                'includeTeamDriveItems': True, 
                                'supportsTeamDrives': True}).GetList()

    drive_dict = {}    
    for file in drive_list: # hmm the fact that this is static ID we can make into dictioanry
        drive_dict[file['title']] =  file['id']
    
    return drive_dict

def upload_to_team_drive_folder(folder_id, file_path, file_name):    
    # dont set title or mimetype in order to make it default to actual files name and dtype
    f = drive.CreateFile({
        'title': file_name,
        'parents': [{
            'kind': 'drive#fileLink',
            'teamDriveId': '0AHSxuxDy84zYUk9PVA',
            'id': folder_id
        }]
    })
    f.SetContentFile(file_path)

    f.Upload(param={'supportsTeamDrives': True})
