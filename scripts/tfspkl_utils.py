import glob
import os
import string
import sys

import mat73
import pandas as pd
from utils import lcs


def get_electrode_ids(CONFIG, conversation):
    """[summary]

    Args:
        conversation ([type]): [description]

    Returns:
        [type]: [description]
    """
    if CONFIG['project_id'] == 'podcast':
        elec_files = glob.glob(
            os.path.join(conversation, 'preprocessed_all', '*.mat'))
    elif CONFIG['project_id'] == 'tfs':
        elec_files = glob.glob(
            os.path.join(conversation, 'preprocessed', '*.mat'))
    else:
        print('Incorrect Project ID')
        sys.exit()

    elec_ids_list = sorted(
        list(
            map(lambda x: int(os.path.splitext(x)[0].split('_')[-1]),
                elec_files)))

    return elec_ids_list


def get_common_electrodes(CONFIG, convs):
    """[summary]

    Args:
        convs ([type]): [description]

    Returns:
        [type]: [description]
    """
    all_elec_ids_list = [
        get_electrode_ids(CONFIG, conversation) for conversation in convs
    ]
    all_elec_labels_list = [
        get_electrode_labels(conversation) for conversation in convs
    ]

    common_electrodes = list(set.intersection(*map(set, all_elec_ids_list)))
    common_labels = sorted(list(
        set.intersection(*map(set, all_elec_labels_list))),
                           key=lambda x: all_elec_labels_list[0].index(x))

    common_labels = [common_labels[elec - 1] for elec in common_electrodes]

    return common_electrodes, common_labels


def get_conversation_list(CONFIG, subject=None):
    """Returns list of conversations

    Arguments:
        CONFIG {dict} -- Configuration information
        set_str {string} -- string indicating set type (train or valid)

    Returns:
        list -- List of tuples (directory, file, idx, common_electrode_list)
    """
    if CONFIG['subject'] != '777':
        conversations = sorted(
            glob.glob(os.path.join(CONFIG["CONV_DIRS"], '*conversation*')))

        return conversations
    else:
        if subject is None:
            subject = CONFIG['subject']
        CONV_DIRS = CONFIG["DATA_DIR"] + '/%s/' % str(subject)
        conversations = sorted(
            glob.glob(os.path.join(CONV_DIRS, '*conversation*')))

    return conversations


def extract_conversation_contents(CONFIG, conversation):
    """Return labels (lines) from conversation text

    Args:
        file ([type]): [description]
        ex_words ([type]): [description]

    Returns:
        list: list of lists with the following contents in that order
                ['word', 'onset', 'offset', 'accuracy', 'speaker']
    """
    df = pd.read_csv(conversation,
                     sep=' ',
                     header=None,
                     names=['word', 'onset', 'offset', 'accuracy', 'speaker'])
    df['word'] = df['word'].str.strip()

    # create a boolean column if the word is in exclude_words
    df = df[~df['word'].isin(CONFIG["exclude_words"])]

    # create a booleam column if the word is a nonword or not
    df['is_nonword'] = df['word'].isin(CONFIG['non_words'])

    df = df.reset_index(drop=True)
    df = df.reset_index()

    return df


def first_level_alignment(args, df):

    # Remove punctuations from conversation datum (because cloze datum doesn't have it)
    datum_without_punctuation = df['word'].apply(
        lambda x: x.translate(str.maketrans('', '', string.punctuation)))

    # Load the cloze datum
    cloze_file = os.path.join(args['DATA_DIR'], 'podcast-datum-cloze.csv')
    cloze_df = pd.read_csv(cloze_file, sep=',')

    # Align conversation datum and cloze datum
    mask1, mask2 = lcs(list(datum_without_punctuation), list(cloze_df.word))
    df.loc[mask1, 'cloze'] = list(cloze_df.loc[mask2, 'cloze'])

    return df


def second_level_alignment(CONFIG, df):
    transcript_df = tokenize_podcast_transcript(CONFIG)

    transcript_df['word_without_punctuation'] = transcript_df['word'].apply(
        lambda x: x.translate(str.maketrans('', '', ",.")))

    mask1, mask2 = lcs(list(transcript_df.word_without_punctuation),
                       list(df.word))

    df = df.rename(columns={'word': 'datum_word'})
    for column in df.columns:
        transcript_df[column] = None  # np.nan == np.nan --> False
        transcript_df.loc[mask1, column] = list(df.loc[mask2, column])

    # Pre-fill with 'Speaker2' to avoid issues downstream (find_switch_points)
    transcript_df['speaker'] = 'Speaker2'

    return transcript_df


def combine_podcast_datums(CONFIG, conversation):
    """[summary]

    Note: This function was exclusively written to handle podcast label creation
    which is a combination of
    1. transcript
    2. cloze datum
    3. conversation datum

    Args:
        CONFIG ([type]): [description]
        conversation ([type]): [description]

    Returns:
        [type]: [description]
    """
    datum_df = extract_conversation_contents(CONFIG, conversation)
    datum_df = first_level_alignment(CONFIG, datum_df)
    datum_df = second_level_alignment(CONFIG, datum_df)

    return datum_df


def get_electrode_labels(conversation_dir):
    """Read the header file electrode labels

    Args:
        conversation_dir (str): conversation folder name/path

    Returns:
        list: electrode labels
    """
    try:
        header_file = glob.glob(
            os.path.join(conversation_dir, 'misc', '*_header.mat'))[0]
    except IndexError:
        raise ValueError('Header File Missing')

    if not os.path.exists(header_file):
        return

    header = mat73.loadmat(header_file)
    labels = header.header.label

    return labels


def tokenize_transcript(file_name):
    # Read all words and tokenize them
    with open(file_name, 'r') as fp:
        data = fp.readlines()

    data = [item.strip().split(' ') for item in data]
    data = [item for sublist in data for item in sublist]
    return data


def tokenize_podcast_transcript(CONFIG):
    """Tokenize the podcast transcript and return as dataframe
    Args:
        args (Namespace): namespace object containing project parameters
                            (command line arguments and others)
    Returns:
        DataFrame: containing tokenized transcript
    """
    story_file = os.path.join(CONFIG['DATA_DIR'], 'podcast-transcription.txt')

    data = tokenize_transcript(story_file)

    df = pd.DataFrame(data, columns=['word'])

    return df
