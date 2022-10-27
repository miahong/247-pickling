import os
import torch
import json
import pandas as pd
from pprint import pprint
from transformers import AutoModelForCausalLM, AutoModelForSeq2SeqLM, AutoTokenizer, GPT2TokenizerFast, GPTNeoXTokenizerFast
from accelerate import init_empty_weights, infer_auto_device_map, load_checkpoint_and_dispatch

CAUSAL_MODELS = [
    # "gpt2",
    # "gpt2-medium",
    # "gpt2-large",
    # "gpt2-xl",
    # "distilgpt2",
    "EleutherAI/gpt-neo-125M",
    "EleutherAI/gpt-neo-1.3B",
    "EleutherAI/gpt-neo-2.7B",
    "EleutherAI/gpt-neox-20b",
    # "facebook/opt-125m",
    # "facebook/opt-350m",
    # "facebook/opt-1.3b",
    # "facebook/opt-2.7b",
    # "facebook/opt-6.7b",
    # "facebook/opt-30b",
    # 'bloom',
    # 'bigscience/bloom-560m',
    # 'bigscience/bloom-1b7',
    # 'bigscience/bloom-3b',
    # 'bigscience/bloom-7b1',
]
SEQ2SEQ_MODELS = ["facebook/blenderbot_small-90M"]

CLONE_MODELS = ["EleutherAI/gpt-neox-20b", "facebook/opt-6.7b", "facebook/opt-30b"]

# TODO: Add MLM_MODELS (Masked Language Models)


def download_tokenizer_and_model(
    CACHE_DIR, tokenizer_class, model_class, model_name, local_files_only
):
    """Cache (or load) the model and tokenizer from the model repository (or cache).

    Args:
        CACHE_DIR (str): path where the model and tokenizer will be cached.
        tokenizer_class (Tokenizer): Tokenizer class to be instantiated for the model.
        model_class (Huggingface Model): Model class corresponding to model_name.
        model_name (str):  Model name as seen on https://hugginface.co/models.
        local_files_only (bool, optional): False (Default) if caching and True if loading from cache.

    Returns:
        tuple: (tokenizer, model)
    """
    print("Downloading model")

    max_gpu_mem = int(60e9)
    max_cpu_mem = int(550e9)
    max_memory = {
        0: max_gpu_mem,
        1: max_gpu_mem,
        2: max_gpu_mem,
        3: max_gpu_mem,
        "cpu": max_cpu_mem
    }

    # if torch.cuda.is_bf16_supported():
    #     print('cuda bf16 Yes')
    #     print()

    model = model_class.from_pretrained(
        model_name,
        output_hidden_states=True,
        cache_dir=CACHE_DIR,
        local_files_only=local_files_only,
        device_map="auto", 
        offload_folder="offload", 
        torch_dtype=torch.bfloat16,
        max_memory=max_memory,     
        
    )
    # for downloading models
    # model = model_class.from_pretrained(
    #     model_name,
    #     output_hidden_states=True,
    #     cache_dir=CACHE_DIR,
    #     local_files_only=local_files_only,    
        
    # )

    print("Downloading tokenizer")
    print("PRINT MODEL NAME: {}".format(model_name))

    if 'EleutherAI/gpt-neox-20b' in model_name:
        
        # tokenizer = GPT2TokenizerFast.from_pretrained(
        #     "gpt2",add_prefix_space=True,
        #     cache_dir=CACHE_DIR,
        #     local_files_only=local_files_only
        # )
        # "/scratch/gpfs/mh6546/.cache/EleutherAI/gpt-neox-20b"  GPT2TokenizerFast
        tokenizer = GPTNeoXTokenizerFast.from_pretrained(
        # tokenizer = tokenizer_class.from_pretrained(
        # tokenizer = GPT2TokenizerFast.from_pretrained(
            "/scratch/gpfs/mh6546/.cache/EleutherAI/gpt-neox-20b",add_prefix_space=True,
            cache_dir=CACHE_DIR,
            local_files_only=local_files_only
        )

    else:
        tokenizer = tokenizer_class.from_pretrained(
                model_name,
                add_prefix_space=True,
                cache_dir=CACHE_DIR,
                local_files_only=local_files_only,
            )
    
    print("PRINT tokenizer: {}".format(tokenizer))
    print()
    
    return (model, tokenizer)


def clone_model_repo(
    CACHE_DIR,
    tokenizer_class,
    model_class,
    model_name,
    local_files_only=False,
):
    """Cache (load) the model and tokenizer from the model repository (cache).

    Args:
        CACHE_DIR (str): path where the model and tokenizer will be cached.
        tokenizer_class (Tokenizer): Tokenizer class to be instantiated for the model.
        model_class (Huggingface Model): Model class corresponding to model_name.
        model_name (str):  Model name as seen on https://hugginface.co/models.
        local_files_only (bool, optional): False (Default) if caching and True if loading from cache.

    Returns:
        tuple or None: (tokenizer, model) if local_files_only is True
                        None if local_files_only is False.
    """
    model_dir = os.path.join(CACHE_DIR, model_name)
    print("RUNNING in clone_model_repo")
    if local_files_only:
        if os.path.exists(model_dir):
            if 'EleutherAI/gpt-neox-20b' in model_name:
                print('In clone_model_repo, Model is recognized as neox-20b\n')
                model, tokenizer = download_tokenizer_and_model(
                CACHE_DIR, GPT2TokenizerFast, model_class, model_dir, local_files_only
            )
            else:
                model, tokenizer = download_tokenizer_and_model(
                    CACHE_DIR, tokenizer_class, model_class, model_dir, local_files_only
                )
            return model, tokenizer
        else:
            print(f"Model directory {model_dir} does not exist")
    else:
        try:
            if (
                "tiger" in os.uname().nodename
            ):  # probably redundant, but just in case we are on tiger
                os.system("module load git")

            os.system(f"git lfs install")
            os.system(f"git clone https://huggingface.co/{model_name} {model_dir}")
        except:
            # FIXME: Raise appropriate exception
            print("Possible git lfs version issues")
    


def set_cache_dir():
    CACHE_DIR = os.path.join(os.path.dirname(os.getcwd()), ".cache")
    os.makedirs(CACHE_DIR, exist_ok=True)
    return CACHE_DIR


def download_tokenizers_and_models(model_name=None, local_files_only=False, debug=True):
    """This function downloads the tokenizer and model for the specified model name.

    Args:
        model_name (str, optional): Model name as seen on https://hugginface.co/models. Defaults to None.
        local_files_only (bool, optional): False (Default) if caching and True if loading from cache.
        debug (bool, optional): Check if caching was successful. Defaults to True.

    Returns:
        dict: Dictionary with model name as key and (tokenizer, model) as value.
    """
    CACHE_DIR = set_cache_dir()

    if model_name is None:
        print("Input argument cannot be empty")
        return

    if model_name == "causal" or model_name in CAUSAL_MODELS:
        model_class = AutoModelForCausalLM
        MODELS = CAUSAL_MODELS if model_name == "causal" else [model_name]
    elif model_name == "seq2seq":
        model_class = AutoModelForSeq2SeqLM
        MODELS = SEQ2SEQ_MODELS if model_name == "seq2seq" else [model_name]
    else:
        print("Invalid Model Name")
        exit(1)

    model_dict = {}
    for model_name in MODELS:
        print(f"Model Name: {model_name}")

        cache_function = (
            clone_model_repo
            if model_name in CLONE_MODELS
            else download_tokenizer_and_model
        )

        model_dict[model_name] = cache_function(
            CACHE_DIR,
            AutoTokenizer,
            model_class,
            model_name,
            local_files_only,
        )

        # check if caching was successful
        if debug:
            print("Checking if model has been cached successfully")
            try:
                cache_function(
                    CACHE_DIR,
                    AutoTokenizer,
                    model_class,
                    model_name,
                    True,
                )
            except:
                print(f"Caching of {model_name} failed")

    return model_dict


if __name__ == "__main__":
    download_tokenizers_and_models("causal", local_files_only=False, debug=True)