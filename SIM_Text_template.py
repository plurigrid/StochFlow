import numpy as np
import torch
import torch.nn as nn
from scipy.integrate import solve_ivp
from scipy.integrate import quad
from sentence_transformers import SentenceTransformer
from sentence_transformers import util 

class TextStochasticInterpolantModel:
    def __init__(self, initial_model, final_model, time_interval, time_step):
        self.initial_model = initial_model
        self.final_model = final_model
        self.time_interval = time_interval
        self.time_step = time_step

        self.interpolant_func = interpolant_func 
        self.diffusivity_func = diffusivity_func

    def generate_samples(self, num_samples):
        initial_samples = self.initial_model.encode(["initial sentence"] * num_samples)
        return self._integrate_samples(initial_samples)

    def _integrate_samples(self, samples):
        def time_derivative(t, y):
            interpolant = self.interpolant_func(t)
            diffusivity = self.diffusivity_func(t)
            dydt = interpolant(y) * diffusivity(y)
            return dydt

        samples_integrated = []
        for sample in samples:
            sol = solve_ivp(time_derivative, [0, self.time_interval], sample, t_eval = [self.time_interval], method = 'RK45')
            samples_integrated.append(sol.y[:, -1])

        return torch.tensor(samples_integrated)

    def likelihood(self, samples):
        return self.final_model.likelihood(samples)

    def cross_entropy(self):
        def integrand(x):
            initial_density_value = self.initial_model.likelihood(x.reshape(-1, 1))
            final_density_value = self.final_model.likelihood(x.reshape(-1, 1))
            return initial_density_value * np.log(initial_density_value / final_density_value)

        integral_result, _ = quad(integrand, -np.inf, np.inf)
        return integral_result

class SentenceEmbeddingDensity:
    def __init__(self, sentence_encoder, mean_embedding):
        self.sentence_encoder = sentence_encoder
        self.mean_embedding = torch.tensor(mean_embedding, dtype = torch.double)  

    def encode(self, sentences):
        return self.sentence_encoder.encode(sentences, convert_to_tensor = True)

    def likelihood(self, samples):
        mean_embedding_expanded = self.mean_embedding.expand(samples.size(0), -1)

        samples_double = samples.double()

        cosine_sims = util.pytorch_cos_sim(samples_double, mean_embedding_expanded)
        prob_values = torch.nn.functional.softmax(cosine_sims, dim=0)
        likelihood_values = prob_values[:, 0].detach().numpy()

        return likelihood_values


def interpolant_func(t):
    return lambda x: x * (1 - t) + t * np.sin(x)

def diffusivity_func(t):
    return lambda x: 1.0 + t * np.cos(x)

if __name__ == "__main__":
    sentence_encoder = SentenceTransformer("bert-base-nli-mean-tokens")

    initial_sentence = "initial sentence"
    final_sentence = "final sentence"

    initial_mean_embedding = sentence_encoder.encode([initial_sentence])
    final_mean_embedding = sentence_encoder.encode([final_sentence])

    initial_model = SentenceEmbeddingDensity(sentence_encoder, initial_mean_embedding)
    final_model = SentenceEmbeddingDensity(sentence_encoder, final_mean_embedding)

    time_interval = 1.0
    time_step = 0.01

    model = TextStochasticInterpolantModel(initial_model, final_model, time_interval, time_step)
    samples = model.generate_samples(num_samples = 1000)
    likelihood = model.likelihood(samples)

    print("Likelihood given samples: ", likelihood)
    print("Samples: ", samples)
