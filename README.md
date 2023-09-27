# DrugEx
 
<img src='figures/logo.png' width=20% align=right>
<p align=left width=70%>
DrugEx is an open-source software library for <i>de novo</i> design of small molecules with deep learning generative models in a multi-objective reinforcement learning framework. The package contains multiple generator architectures and a variety of scoring tools and multi-objective optimisation methods. It has a flexible application programming interface and can readily be used via the command line interface [<a href="sicho_drugex">4</a>] (see [Quick Start](#quick-start) to get to work right away).

## History

This software is a continuation of the original and incremental work of Liu et al.'s DrugEx [<a href="liu_drugex1">1</a>, <a href="liu_drugex2">2</a>, <a href="liu_drugex3">3</a>] and is currently developed by [Gerard van Westen's Computational Drug Discovery](https://twitter.com/cddleiden) group in Leiden, Netherlands. The first version of DrugEx [<a href="liu_drugex1">1</a>] consisted of a recurrent neural network (RNN) single-task agent of gated recurrent units (GRU) which were updated to long short-term memory (LSTM) units in the second version [<a href="liu_drugex2">2</a>], also introducing MOO-based RL and an updated exploitation-exploration strategy. In its third version, [<a href="liu_drugex3">3</a>] generators based on a variant of the transformer and a novel graph-based encoding allowing for the sampling of molecules with specific substructures were introduced. This package builds on these works and provides a unified API with increased usability and flexibile enough for customization. However, new additional features are beeing added as well [<a href="sicho_drugex">4</a>]. Furthermore, the development and traning of QSAR models, used to score molecules during reinforcement learning has been moved to a separate [QSPRpred](https://github.com/CDDLeiden/QSPRPred)-package, which became a useful library in its own right.


## Workflow

The DrugEx package provides classes to standardize, clean and encode molecules for the various deep learning algorithms provided in the package as well as features to set up and monitor training and optimization. The resulting models can be used readily for generation of focused libraries and are easily transferable.

![Fig1](figures/TOC_figure.png)

<!-- Introduction
=============
Due to the large drug-like chemical space available to search for feasible drug-like molecules, rational drug design often starts from specific scaffolds to which side chains/substituents are added or modified. With the rapid growth of the application of deep learning in drug discovery, a variety of effective approaches have been developed for de novo drug design. In previous work, we proposed a method named DrugEx, which can be applied in polypharmacology based on multi-objective deep reinforcement learning. However, the previous version is trained under fixed objectives similar to other known methods and does not allow users to input any prior information (i.e. a desired scaffold). In order to improve the general applicability, we updated DrugEx to design drug molecules based on scaffolds which consist of multiple fragments provided by users. In this work, the Transformer model was employed to generate molecular structures. The Transformer is a multi-head self-attention deep learning model containing an encoder to receive scaffolds as input and a decoder to generate molecules as output. In order to deal with the graph representation of molecules we proposed a novel positional encoding for each atom and bond based on an adjacency matrix to extend the architecture of the Transformer. Each molecule was generated by growing and connecting procedures for the fragments in the given scaffold that were unified into one model. Moreover, we trained this generator under a reinforcement learning framework to increase the number of desired ligands. As a proof of concept, our proposed method was applied to design ligands for the adenosine A2A receptor (A2AAR) and compared with SMILES-based methods. The results demonstrated the effectiveness of our method in that 100% of the generated molecules are valid and most of them had a high predicted affinity value towards A2AAR with given scaffolds.  -->

<!-- <b>Keywords</b>: deep learning, reinforcement learning, policy gradient, drug design, Transformer, multi-objective optimization</p> -->

<!-- Deep learning Archietectures
====================
![Fig2](figures/fig_2.png)

Examples
=========
![Fig3](figures/fig_3.png) -->

# Quick Start

> A small step for exploring the drug space in need, a giant leap for exploiting a healthy state indeed.


## Installation

DrugEx can be installed with pip like so:

```bash
pip install git+https://github.com/CDDLeiden/DrugEx.git@master
```

### Optional Dependencies

**[QSPRPred](https://github.com/CDDLeiden/QSPRPred.git)** - Optional package to install if you want to use the command line interface of DrugEx, which requires the models to be serialized with this package. It is also used by some examples in the tutorial. Install DrugEx with the following command if you want these features:

```bash
pip install "drugex[qsprpred] @ git+https://github.com/CDDLeiden/DrugEx.git@master"
```

**[RAscore](https://github.com/reymond-group/RAscore)** - If you want to use the Retrosynthesis Accessibility Score in the desirability function.
- The installation of RAscore might downgrade the scikit-Learn packages. If this happens, scikit-Learn should be re-upgraded.


## Use

After installation, you will have access to various command line features, but you can also use the Python API directly. Documentation for the current version of both is available [here](https://cddleiden.github.io/DrugEx/docs/). For a quick start, you can also check out our [Jupyter notebook tutorial](./tutorial), which documents the use of the Python API to build different types of models, or take look at the [CLI examples](https://cddleiden.github.io/DrugEx/docs/use.html#cli-example). The tutorials as well as the documentation are still work in progress, and we will be happy for any contributions where it is still lacking.

This repository contains almost all models implemented throughout DrugEx history. We also make the following pretrained models available to be used with this package. You can retrieve them from the following table (not all models are available at this moment, but we will keep adding them):

<table style="text-align: center;">
  <thead>
    <tr>
      <th rowspan="3">Model</th>
      <th colspan="2">RNN</th>
      <th colspan="2"><a href="https://doi.org/10.1186/s13321-023-00694-z">SMILES-Based Transformer</a></th>
      <th colspan="2"><a href="https://doi.org/10.1186/s13321-023-00694-z">Graph-Based Transformer</a></th>
    </tr>
    <tr>
      <th colspan="2">type</th>
      <th colspan="4">fragmentation</th>
    </tr>
    <tr>
      <th><a href="https://doi.org/10.1186/s13321-019-0355-6">GRU</a></th>
      <th><a href="https://doi.org/10.1186/s13321-021-00561-9">LSTM</a></th>
      <th>BRICS</th>
      <th>RECAP</th>
      <th>BRICS</th>
      <th>RECAP</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>ChEMBL 27</td>
      <td>-</td>
      <td><a href="https://doi.org/10.5281/zenodo.7096837">Zenodo</a></td>
      <td>-</td>
      <td>-</td>
      <td><a href="https://doi.org/10.5281/zenodo.7096823">Zenodo</a></td>
      <td>-</td>
    </tr>
    <tr>
      <td>ChEMBL 31</td>
      <td><a href="https://doi.org/10.5281/zenodo.7550739">Zenodo</a></td>
      <td><a href="https://doi.org/10.5281/zenodo.7378916">Zenodo</a></td>
      <td>-</td>
      <td>-</td>
      <td><a href="https://doi.org/10.5281/zenodo.7085629">Zenodo</a></td>
      <td>-</td>
    </tr>
    <tr>
      <td><a href="https://doi.org/10.1186/s13321-022-00672-x">Papyrus</a> <a href="https://doi.org/10.5281/zenodo.7019874">05.5</a></td>
      <td><a href="https://doi.org/10.5281/zenodo.7550792">Zenodo</a></td>
      <td><a href="https://doi.org/10.5281/zenodo.7378923">Zenodo</a></td>
      <td><a href="https://doi.org/10.5281/zenodo.7635064">Zenodo</a></td>
      <td><a href="https://doi.org/10.5281/zenodo.7622774">Zenodo</a></td>
      <td><a href="https://doi.org/10.5281/zenodo.7085421">Zenodo</a></td>
      <td><a href="https://doi.org/10.5281/zenodo.7622738">Zenodo</a></td>
    </tr>
  </tbody>
</table>

### Hardware Requirements

The DrugEx toolkit offers a variety of models with varying complexities, each with its unique hardware requirements. In order to enable the full suite of models, the user must have a GPU compatible with CUDA 9.2, with a minimum of 8 GB of video memory. This is to facilitate that the models can be transferred to the GPU along with sufficiently large training batches. 

It is noteworthy, however, that even on a suboptimal configuration, it should be possible to fine-tune and optimize the basic sequential RNN model using reinforcement learning techniques if a pretrained model is used. Regarding the two transformers, we recommend leveraging multiple GPUs to increase throughput via parallelization, automated by the DrugEx package. This technique divides the model's workload across multiple GPUs, enabling the system to handle more significant volumes of data at a faster rate than when using a single GPU.

# License

The software is licensed under the standard MIT license, which means it is free to use also in commercial applications as long as the copyright terms of the license are preserved. You can view the [LICENSE](./LICENSE) file for the full terms. If you have questions about the license or the use of the software in your organization, please, contact Gerard J.P. van Westen:

   [Gerard J.P. van Westen](mailto:gerard@lacdr.leidenuniv.nl): gerard@lacdr.leidenuniv.nl 

# Current Development Team

- [M. Sicho](https://github.com/martin-sicho)
- [S. Luukkonen](https://github.com/sohviluukkonen)
- [H. van den Maagdenberg](https://github.com/HellevdM)
- [L. Schoenmaker](https://github.com/LindeSchoenmaker)
- [O. Béquignon](https://github.com/OlivierBeq)

# Contributions

If you find that there is something missing, have a question, or you just want to contribute a new model or feature, please, feel free to open an issue to initiate a discussion. We are more than happy to improve the package with your contributions, bug reports and ideas. After the feature is discussed in its designated issue, the best way to contribute is to fork the repository, make your changes and then create a pull request. We will then review your changes and merge them into the main repository. Alternatively, you can contact us directly via [email](mailto:cdd@lacdr.leidenuniv.nl).

# Acknowledgements

We would like to thank the following people for significant contributions:

- [Xuhan Liu](https://github.com/XuhanLiu)
  - author of the original idea to develop the DrugEx models and code, we are happy for his continuous support of the project

We also thank the following Git repositories that gave Xuhan a lot of inspirations:
   
1. [REINVENT](https://github.com/MarcusOlivecrona/REINVENT)
2. [ORGAN](https://github.com/gablg1/ORGAN)
3. [SeqGAN](https://github.com/LantaoYu/SeqGAN)

# References

<a name="liu_drugex1"></a> [1] [Liu X., Ye K., van Vlijmen H.W.T, IJzerman A.P., van Westen G.J.P. An exploration strategy improves the diversity of de novo ligands using deep reinforcement learning: a case for the adenosine A2A receptor. Journal of cheminformatics. 2019;11(1):35.](https://jcheminf.biomedcentral.com/articles/10.1186/s13321-019-0355-6)

<a name="liu_drugex2"></a> [2] [Liu X, Ye K, van Vlijmen H.W.T, Emmerich M.T.M., IJzerman AP, van Westen G.J.P. DrugEx v2: De Novo Design of Drug Molecule by Pareto-based Multi-Objective Reinforcement Learning in Polypharmacology. Journal of cheminformatics 2021:13(1):85.](https://doi.org/10.1186/s13321-021-00561-9) 

<a name="liu_drugex3"></a> [3] [Liu, X., Ye, K., van Vlijmen, H.W.T. IJzerman A.P., van Westen G.J.P. DrugEx v3: scaffold-constrained drug design with graph transformer-based reinforcement learning. J Cheminform 15, 24 (2023).](https://doi.org/10.1186/s13321-023-00694-z)

<a name="sicho_drugex"></a> [4] [Sicho M., Luukkonen S., van den Maagdenberg H.W., Schoenmaker L., Béquignon O.J.M., van Westen G.J.P. DrugEx: Deep Learning Models and Tools for Exploration of Drug-like Chemical Space.](https://chemrxiv.org/engage/chemrxiv/article-details/6408c3f5cc600523a3df2174)
