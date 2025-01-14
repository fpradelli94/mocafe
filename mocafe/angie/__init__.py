"""
This subpackage contains all the modules to simulate an angiogenesis model in FEniCS,
using an hybrid Phase-Field/agent approach. By default, the algorithms used are the same presented by
Travasso and collaborators :cite:`Travasso2011a`.

It is composed of the following modules:

* ``af_sourcing``, which contains classes and methods to manage source cells.
* ``forms``, which contains the implementation in Unified Form Language (UFL) of the PDEs presented in Travasso et al.
  :cite:`Travasso2011a`.
* ``tipcells``, which contains the classes and modules to manage tip cells.
* ``base_classes``, which contains classes and methods shared among the angie modules.

You can find full documentation for each module in the "Submodules" section below.

"""