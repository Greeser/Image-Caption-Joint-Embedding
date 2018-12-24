import numpy
import copy
from collections import OrderedDict
from settings import config
import torch
from torch.autograd import Variable
import pickle
from random import shuffle
import deepdish as dd

class KFoldCrossValidation:
    """
    Handles splitting data into folds and serving each train/test through a generator.
    """

    def split(self, a, n):
        k, m = divmod(len(a), n)
        return (a[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))

    def __init__(self, data, k):    

    	# set up for iteration    
        self.k = k
        self.idx = 0      
        
        # zip list and shuffle it
        d = list(zip(data[0], data[1]))
        shuffle(d)

        # create split array
        gen = self.split(d, k)
        self.splits = []
        for i in gen:
        	self.splits.append(i)

    def __iter__(self):
        return self

    def __next__(self):    	
        if self.idx == self.k:
            raise StopIteration

        test = self.splits[self.idx]
        shuffle(test)

        train = []
        for i, split in enumerate(self.splits):
        	if i != self.idx:
        		shuffle(split)
        		train += split

        shuffle(train)

        self.idx += 1

        return train, test, self.idx

class Data:
    """
    Will default to using k_fold cross validation.
    Set the "self.use_test_set" to process the test set.
    """
    def __init__(self, create_dict=False):

        # Load captions as array of strings corresponding to an array of image feature vectors
        self.load_dataset(name=config["dataset"])
        self.reset()

        if create_dict:
        	self.create_dictionaries()

    def k_folds(self, k=5):        
        return KFoldCrossValidation(self.data, k)

    def process(self, train, test, fold, create_dictionaries=True):
        print("\n[PROCESSING] fold", fold) 
        self.train = list(zip(*train))
        self.test = list(zip(*test))
        self.reset()
        if create_dictionaries:
            self.create_dictionaries()

    def reset(self):
    	# Reset counter & batch size
        self.batch_size = config["batch_size"]        
        self.batch_number = 0
        self.previous_batch_number = 0   
        self.use_test_set = False     
        return

    def test_set(self, mode):
        """
        Will switch to iterating over the test set or train set.
        """
        if mode:
            self.use_test_set = True
            self.previous_batch_number = self.batch_number
            self.batch_number = 0
        else:
            self.use_test_set = False
            self.batch_number = self.previous_batch_number        

    def __iter__(self):
        return self
    
    def __next__(self):        
        """
        Return a batch of data ready to go into the model
        """

        data_set = self.train
        if self.use_test_set:
        	data_set = self.test      	

        # Upper and lower indexes for the batches
        upper_idx = (self.batch_number+1)*self.batch_size
        lower_idx = self.batch_number*self.batch_size

        # If our lower index is in the bounds of our data, we can return a new batch
        if lower_idx < len(data_set[0]):            
            self.batch_number += 1 # Increment the batch number so next-time we will return the next batch
            captions = data_set[0][lower_idx:upper_idx] # Extract caption batch
            image_features = data_set[1][lower_idx:upper_idx] # Extract image feature batch
            captions, image_features = self.preprocess_data(captions, image_features) # Preprocess our data, converting raw text to embedded numbers etc                        
            return captions, image_features
            
        self.batch_number = 0
        raise StopIteration
    
    def load_dataset(self, name='f8k', path_to_data = 'data/', test=False):
        """
        Load captions and image features
        """            
        loc = path_to_data + name + '/'

        # Captions        
        cap_file_name = loc+name+'_caps.h5'
        captions = dd.io.load(cap_file_name)                

        # Image features
        ims = numpy.load(loc+name+'_ims.npy')
                
        self.data = (captions, ims)
        self.train = self.data
        self.test = self.data

        print("[LOADED]", name, "dataset") 

        if len(self.data[0]) != len(self.data[1]):
            print("Captions do not match image features one to one for dataset!")           

        return
    
    def load_dictionaries(self):    	
        self.word_to_index = pickle.load(open('dict/word_to_index.pkl', 'rb'))
        self.index_to_word = pickle.load(open('dict/index_to_word.pkl', 'rb'))
        print("[LOADED] dictionaries from dict/") 
        return

    def save_dictionaries(self):
        # Save dictionaries        
        with open('dict/word_to_index.pkl', 'wb') as file:
            pickle.dump(self.word_to_index, file)
        with open('dict/index_to_word.pkl', 'wb') as file:
            pickle.dump(self.index_to_word, file)
        return    	

    def create_dictionaries(self):
        """
        Create the dictionaries to go from a word to an index and an index to a words.
        """        
        captions = self.train[0]

        # TODO: Add beginning and end of setence tokens thats not zero
        self.word_to_index = {'<blank>':0, '<sos>':1, '<eos>':2, '<unk>':3}
        self.index_to_word = {0:'<blank>', 1:'<sos>', 2:'<eos>', 3:'<unk>'}
        pad = len(self.word_to_index)

        words = set()                
        for idx, caption in enumerate([item for caption_set in captions for item in caption_set]):  
            for word in caption.split():  
                words.add(word)                

        for idx, word in enumerate(words):
            self.word_to_index[word] = idx + pad
            self.index_to_word[idx+pad] = word

        print("[INIT] dictionaries")
        print("[CONTAINS]", len(self.word_to_index)-2, "words")        
        return

    def preprocess_data(self, captions, image_features, n_words=10000):
        """
        Convert raw data to go into the model.
        """               
        def get_seq(caption): 
            seq = [self.word_to_index[word] if word in self.word_to_index.keys() else 1 for word in caption.split()]       	
            seq.insert(0, self.word_to_index["<sos>"])
            seq.append(self.word_to_index["<eos>"])

            if len(seq) > config["max_word_emb"]:
                print("Warning: max_word_emb size exceeded. Check your settings.")
                         
            return seq

        # Convert a caption to an array of indexes of words from the dictionary, self.word_to_index  
        sequences = []               
        for idx, caption in enumerate(captions):
            sequences.append([get_seq(i) for i in caption])         


        # Create a 3D matrix
        x = len(sequences)
        y = max([len(i) for i in sequences])
        z = max([len(j) for i in sequences for j in i])
        z = config["max_word_emb"]

        processed_captions = numpy.zeros((x, y, z)).astype('int64')

        # for an array of seqs
        for idx, seq in enumerate(sequences):        	
            # for a seq array
            for jdx, item in enumerate(seq):
                # for each element in the seq array
                for kdx, element in enumerate(item):
                    # set value in matrix
                    processed_captions[idx][jdx][kdx] = element

        # Just convert image features to numpy array
        processed_image_features = numpy.asarray(image_features, dtype=numpy.float32)

        if torch.cuda.is_available() and config["cuda"] == True:
            return Variable(torch.from_numpy(processed_captions)).cuda(), Variable(torch.from_numpy(processed_image_features)).cuda()
        
        return Variable(torch.from_numpy(processed_captions)), Variable(torch.from_numpy(processed_image_features))


