<p align="center">
  <a href="https://imgur.com/7bPAtl1">
	  <img src="https://i.imgur.com/7bPAtl1.png" title="source: imgur.com" width=200/>
  </a>
</p>

# Mocafe: modeling cancer with FEniCS  
  
> A Python package based on [FEniCS](https://fenicsproject.org/) to develop and simulate Phase Field mathematical models for cancer  
  
The purpose of Mocafe is to provide an open source and efficient implementation of Phase Field mathematical models of cancer development and angiogenesis. 

Use Mocafe to: 
* reproduce important cancer phase field model (also in parallel with `MPI`);  
* understand them better inspecting the code, and changing the parameters;  
* integrate these models in yours [FEniCS](https://fenicsproject.org/) scripts.

## Cite
Mocafe is published at:

> Franco Pradelli, Giovanni Minervini, Silvio C E Tosatto, Mocafe: a comprehensive Python library for simulating cancer development with Phase Field Models, Bioinformatics, 2022;, btac521, https://doi.org/10.1093/bioinformatics/btac521

## Documentation
To ease Mocafe usage by every user, we provide an extensive documentation along with the package. 
You can find it here: [link to documentation](https://biocomputingup.github.io/mocafe/build/html/index.html).
  
## Installation

### All users
**If you don't have FEniCS installed**, you can find a step-by-step guide on the installation of FEniCS and Mocafe
on the [Installation page](https://biocomputingup.github.io/mocafe/build/html/installation.html).

### FEniCS users
Every system with FEniCS installed can install and use Mocafe just like any other Python Package. You can use `pip3` to install it:
```
pip3 install git+https://github.com/BioComputingUP/mocafe#egg=mocafe
```
And test it running:
```
python3 -m mocafe
```

### Singularity users
We prepared a Singularity definition file to easily create a Mocafe container to run on your system. See the 
[Installation page](https://biocomputingup.github.io/mocafe/build/html/installation.html) for further details.

## Demos
 
Mocafe allows anyone to simulate a phase field cancer models just as any other FEniCS Python script.
Please refer to the [demo gallery](https://biocomputingup.github.io/mocafe/build/html/demo_doc/index.html)  in the Mocafe documentation for extensive usage examples. Currently, the demos include:

| Model                                                                                                                                                                           | 2D                                                     | 3D                                                     |
|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------|--------------------------------------------------------|
| A **prostate cancer model** first proposed by Lorenzo et al. in 2016 [^Lorenzo2016], both in 2D and in 3D;                                                                      | ![2D_prostate_cancer](https://i.imgur.com/zlLAeso.png) | ![3D_prostate_cancer](https://i.imgur.com/VOQ8c7u.png) |
| An **angiogenesis model** first proposed by Travasso et al. in 2011 [^Travasso2011], both in 2D and in 3D (3D adaptation first reported by Guerra et al. in 2012 [^Guerra2012]) | ![2D_angiogenesis](https://i.imgur.com/JqZ6Lr3.png)    | ![3D_angiogenesis](https://i.imgur.com/6R1mJ4d.png)    |
 
## Release History  

* 05 Sep 2022: Improved saving simulation; added possibility to interrupt and restart simulation with `save_tip_cells` and `load_tip_cells_from_json`. Improved parameters management.
* 04 Sep 2022: Improved and fixed method to estimate capillaries and cancer areas.
* 01 Aug 2022: Added feature for saving simulations
* 25 Jul 2022: Mocafe published
* 24 Jan 2022: Released Mocafe 1.0.0 
  
## Meta  
  
Franco Pradelli (franco.pradelli94@gmail.com), Giovanni Minervini, and Silvio Tosatto  
[https://github.com/BioComputingUP/mocafe](https://github.com/BioComputingUP/mocafe)

## License
This work is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License. To view a copy of this license, visit http://creativecommons.org/licenses/by-nc/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
  
## Contributing  
We welcome any feedback and we thank you if you're considering to contribute to our project.
  
Mocafe follows the standard "Fork & Pull" contributing model of GitHub (more information [here](https://docs.github.com/en/get-started/quickstart/contributing-to-projects)).

Briefly, if you'd like to make a change to Mocafe you can:

1. create an account on GitHub 
2. fork this project 
3. make a local clone with `git clone https://github.com/your_account/mocafe.git`
4. make changes on the local copy 
5. commit changes git commit -a -m "my message"
6. push to your GitHub account with `git push origin`
7. create a Pull Request (PR) from your GitHub fork (go to your fork's webpage and click on "Pull Request." You can then add a message to describe your proposal.)

If you'd like to add a mathematical model to Mocafe, the `litforms` package is the right place for it. 
It is sufficient to add a module containing, at least, a method returning the FEniCS `Form` of your model of interest.
Also, consider adding complete documentation and references for it.

 
 [^Lorenzo2016]: Lorenzo, G., Scott, M. A., Tew, K., Hughes, T. J. R., Zhang, Y. J., Liu, L., Vilanova, G., & Gomez, H. (2016). Tissue-scale, personalized modeling and simulation of prostate cancer growth. _Proceedings of the National Academy of Sciences_. https://doi.org/10.1073/pnas.1615791113
 [^Travasso2011]: Travasso, R. D. M., Poiré, E. C., Castro, M., Rodrguez-Manzaneque, J. C., & Hernández-Machado, A. (2011). Tumor angiogenesis and vascular patterning: A mathematical model. _PLoS ONE_, _6_(5), e19989. https://doi.org/10.1371/journal.pone.0019989
 [^Guerra2012]: Dias Soares Quinas Guerra, M. M., & Travasso, R. D. M. (2012). Novel approach to vascular network modeling in 3D. 2012 IEEE 2nd Portuguese Meeting in Bioengineering, ENBENG 2012. https://doi.org/10.1109/ENBENG.2012.6331381

