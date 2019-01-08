config = {
	"num_epochs":300,
	"batch_size":64,
	"word_dimension":1000, # The dimensionality of word embeddings
	"image_dimension":512, # input image dimension : 4096 for VGG, 512 resnet
	"model_dimension":1000, # The dimension of the embedding space,
	"max_word_emb":1000, # the max sequence size
	"dialog_emb":128,
	"learning_rate":0.01,
	"display_freq":4, # how often to display loss : 1 = every batch, 2 = every second batch etc...
	"margin_pairwise_ranking_loss":0.2, # Should be between zero and 1,
	"dataset":"visual_fashion_dialog", # visual_fashion_dialog, deepfashion
	"cuda":True # enable cuda
}