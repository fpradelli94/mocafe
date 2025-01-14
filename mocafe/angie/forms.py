"""
Weak forms of the Phase-Field models related to angiogenesis. Each weak form is a FEniCS UFL Form which can be used
calling a specific method, that returns the form itself.

If you use this model in your research, remember to cite the original paper describing the model:

    Travasso, R. D. M., Poiré, E. C., Castro, M., Rodrguez-Manzaneque, J. C., & Hernández-Machado, A. (2011).
    Tumor angiogenesis and vascular patterning: A mathematical model. PLoS ONE, 6(5), e19989.
    https://doi.org/10.1371/journal.pone.0019989

For a use example see the :ref:`Angiogenesis <Angiogenesis 2D Demo>` and the
:ref:`Angiogenesis 3D <Angiogenesis 2D Demo>` demos.
"""

import fenics
from mocafe.fenut.parameters import Parameters, _unpack_parameters_list


def vascular_proliferation_form(alpha_p, af, af_p, c, v):
    r"""
    Returns the UFL Form for the proliferation term of the vascular tissue as defined by the paper of Travasso et al.
    (2011) :cite:`Travasso2011a`.

    The corresponding term of the equation is (H is the Heaviside function):

    .. math::
       \alpha_p(af_p) \cdot c \cdot H(c)

    Where :math: `af` is the angiogenic factor concentration, and :math: `\alpha_p(af)` represents the proliferation
    rate, that is defined as the follwing function of :math: `af`. The definition of the latter function is the
    following:

    .. math::
       \alpha_p(af) &= \alpha_p \cdot af_p \quad \textrm{if} \quad af>af_p \\
                    &= \alpha_p \cdot af  \quad \textrm{if} \quad 0<af \le af_p \\
                    & = 0 \quad \textrm{if} \quad af \le 0

    Where :math: `\alpha-p` and :math: `af_p` are constants.

    :param alpha_p: costant of the proliferation rate function for the capillaries
    :param af: FEniCS function representing the angiogenic factor distribution
    :param af_p: maximum concentration of angiogenic factor leading to proliferation. If af > af_p, the proliferation
        rate remains alpha_p * af_p
    :param c: FEniCS function representing the capillaries
    :param v: FEniCS test function
    :return: the UFL form for the proliferation term
    """
    # def the proliferation function
    proliferation_function = alpha_p * af
    # def the max value for the proliferation function
    proliferation_function_max = alpha_p * af_p
    # take the bigger between the two of them
    proliferation_function_hysteresis = fenics.conditional(fenics.gt(proliferation_function,
                                                                     proliferation_function_max),
                                                           proliferation_function_max,
                                                           proliferation_function)
    # multiply the proliferation term with the vessel field
    proliferation_term = proliferation_function_hysteresis * c
    # take it oly if bigger than 0
    proliferation_term_heaviside = fenics.conditional(fenics.gt(proliferation_term, 0.),
                                                      proliferation_term,
                                                      fenics.Constant(0.))
    # build the form
    proliferation_term_form = proliferation_term_heaviside * v * fenics.dx
    return proliferation_term_form


def cahn_hillard_form(c: fenics.Variable,
                      c0: fenics.Function,
                      mu: fenics.Function,
                      mu0: fenics.Function,
                      q: fenics.TestFunction,
                      v: fenics.TestFunction,
                      dt,
                      theta,
                      chem_potential,
                      lmbda,
                      M):
    r"""
    Returns the UFL form of a for a general Cahn-Hillard equation, discretized in time using the theta method. The
    method is the same reported by the FEniCS team in one of their demo `1. Cahn-Hillard equation`_ and is briefly
    discussed below for your conveneince.

    .. _1. Cahn-Hillard equation:
       https://fenicsproject.org/olddocs/dolfin/2016.2.0/cpp/demo/documented/cahn-hilliard/cpp/documentation.html

    The Cahn-Hillard equation reads as follows:

    .. math::
       \frac{\partial c}{\partial t} - \nabla \cdot M (\nabla(\frac{d f}{d c}
             - \lambda \nabla^{2}c)) = 0 \quad \textrm{in} \ \Omega

    Where :math: `c` is the unknown field to find, :math: `f` is some kind of energetic potential which defines the
    phase separation, and :math: `M` is a scalar parameter.

    The equation involves 4th order derivatives, so its weak form could not be handled with the standard Lagrange
    finite element basis. However, the equation can be splitted in two second-order equations adding a second unknown
    auxiliary field :math: `\mu`:

    .. math::
       \frac{\partial c}{\partial t} - \nabla \cdot M \nabla\mu  &= 0 \quad \textrm{in} \ \Omega, \\
       \mu -  \frac{d f}{d c} + \lambda \nabla^{2}c &= 0 \quad \textrm{ in} \ \Omega.

    In this way, it is possible to solve this equation using the standard Lagrange basis and, indeed, this
    implementation uses this form.

    :param c: main Cahn-Hillard field
    :param c0: initial condition for the main Cahn-Hillard field
    :param mu: auxiliary field for the Cahn-Hillard equation
    :param mu0: initial condition for the auxiliary field
    :param q: test function for c
    :param v: test function for mu
    :param dt: time step
    :param theta: theta value for theta method
    :param chem_potential: UFL form for the Cahn-Hillard potential
    :param lmbda: energetic weight for the gradient of c
    :param M: scalar parameter
    :return: the UFL form of the Cahn-Hillard Equation
    """
    # Define form for mu (theta method)
    mu_mid = (fenics.Constant(1.0) - theta) * mu0 + theta * mu

    # chem potential derivative
    dfdc = fenics.diff(chem_potential, c)

    # define form
    l0 = ((c - c0) / dt) * q * fenics.dx + M * fenics.dot(fenics.grad(mu_mid), fenics.grad(q)) * fenics.dx
    l1 = mu * v * fenics.dx - dfdc * v * fenics.dx - lmbda * fenics.dot(fenics.grad(c), fenics.grad(v)) * fenics.dx
    form = l0 + l1

    # return form
    return form


def angiogenesis_form(c: fenics.Function,
                      c0: fenics.Function,
                      mu: fenics.Function,
                      mu0: fenics.Function,
                      v1: fenics.TestFunction,
                      v2: fenics.TestFunction,
                      af: fenics.Function,
                      parameters: Parameters = None,
                      **kwargs):
    r"""
    Returns the UFL form for the Phase-Field model for angiogenesis reported by Travasso et al. (2011)
    :cite:`Travasso2011a`.

    The equation reads simply as the sum of a Cahn-Hillard term and a proliferation term (for further details see
    the original paper):

    .. math::
       \frac{\partial c}{\partial t} = M \cdot \nabla^2 [\frac{df}{dc}\ - \epsilon \nabla^2 c]
       + \alpha_p(T) \cdot c H(c)

    Where :math: `c` is the unknown field representing the capillaries, and :

    .. math:: f = \frac{1}{4} \cdot c^4 - \frac{1}{2} \cdot c^2

    .. math::
       \alpha_p(af) &= \alpha_p \cdot af_p \quad \textrm{if} \quad af>af_p \\
                    &= \alpha_p \cdot af  \quad \textrm{if} \quad 0<af \le af_p \\
                    & = 0 \quad \textrm{if} \quad af \le 0

    In this implementation, the equation is splitted in two equations of lower order, in order to make the weak form
    solvable using standard Lagrange finite elements:

    .. math::
       \frac{\partial c}{\partial t} &= M \nabla^2 \cdot \mu + \alpha_p(T) \cdot c H(c) \\
       \mu &= \frac{d f}{d c} - \epsilon \nabla^{2}c

    (New in version 1.4) Specify a parameter for the form calling the function, e.g. with
    ``angiogenesis_form(c, c0, mu, mu0, v1, v2, af, parameters, alpha_p=10, M=20)``. If both a Parameters object and a
    parameter as input are given, the function will choose the input parameter.

    :param c: capillaries field
    :param c0: initial condition for the capillaries field
    :param mu: auxiliary field
    :param mu0: initial condition for the auxiliary field
    :param v1: test function for c
    :param v2: test function  for mu
    :param af: angiogenic factor field
    :param parameters: simulation parameters
    :return:
    """
    # get parameters
    dt, epsilon, M, alpha_p, T_p = _unpack_parameters_list(["dt", "epsilon", "M", "alpha_p", "T_p"],
                                                           parameters,
                                                           kwargs)
    # define theta
    theta = 0.5

    # define chemical potential for the phase field
    c = fenics.variable(c)
    chem_potential = ((c ** 4) / 4) - ((c ** 2) / 2)

    # define total form
    form_cahn_hillard = cahn_hillard_form(c, c0, mu, mu0, v1, v2, dt, theta, chem_potential,
                                          epsilon, M)
    form_proliferation = vascular_proliferation_form(alpha_p, af, T_p,
                                                     c, v1)
    form = form_cahn_hillard - form_proliferation

    return form


def angiogenesis_form_no_proliferation(c: fenics.Function,
                                       c0: fenics.Function,
                                       mu: fenics.Function,
                                       mu0: fenics.Function,
                                       v1: fenics.TestFunction,
                                       v2: fenics.TestFunction,
                                       parameters: Parameters = None,
                                       **kwargs):
    r"""
    (New in version 1.4)
    Returns the UFL form for the Phase-Field model for angiogenesis reported by Travasso et al. (2011)
    :cite:`Travasso2011a`, without the proliferation term.

    The equation reads simply as:

    .. math::
       \frac{\partial c}{\partial t} = M \cdot \nabla^2 [\frac{df}{dc}\ - \epsilon \nabla^2 c]

    Where :math: `c` is the unknown field representing the capillaries, and :

    .. math:: f = \frac{1}{4} \cdot c^4 - \frac{1}{2} \cdot c^2

    In this implementation, the equation is splitted in two equations of lower order, in order to make the weak form
    solvable using standard Lagrange finite elements:

    .. math::
       \frac{\partial c}{\partial t} &= M \nabla^2 \cdot \mu\\
       \mu &= \frac{d f}{d c} - \epsilon \nabla^{2}c

    Specify a parameter for the form calling the function, e.g. with
    ``angiogenesis_form(c, c0, mu, mu0, v1, v2, af, parameters, alpha_p=10, M=20)``. If both a Parameters object and a
    parameter as input are given, the function will choose the input parameter.

    :param c: capillaries field
    :param c0: initial condition for the capillaries field
    :param mu: auxiliary field
    :param mu0: initial condition for the auxiliary field
    :param v1: test function for c
    :param v2: test function  for mu
    :param af: angiogenic factor field
    :param parameters: simulation parameters
    :return:
    """
    # get parameters
    dt, epsilon, M = _unpack_parameters_list(["dt", "epsilon", "M"],
                                             parameters,
                                             kwargs)
    # define theta
    theta = 0.5

    # define chemical potential for the phase field
    c = fenics.variable(c)
    chem_potential = ((c ** 4) / 4) - ((c ** 2) / 2)

    # define total form
    form_cahn_hillard = cahn_hillard_form(c, c0, mu, mu0, v1, v2, dt, theta, chem_potential,
                                          epsilon, M)
    return form_cahn_hillard


def angiogenic_factor_form(af: fenics.Function,
                           af_0: fenics.Function,
                           c: fenics.Function,
                           v: fenics.TestFunction,
                           parameters: Parameters = None,
                           **kwargs):
    r"""
    Returns the UFL form for the equation for the angiogenic factor reported by Travasso et al. (2011)
    :cite:`Travasso2011a`.

    The equation simply considers the diffusion of the angiogenic factor and its consumption by the capillaries
    (for further details see the original paper):

    .. math::
       \frac{\partial af}{\partial t} = D \nabla^2 af - \alpha_T \cdot af \cdot c \cdot H(c)

    Where :math: `af` is the angiogenic factor field, :math: `c` is the capillaries field, and :math: `H(c)` is the
    Heaviside function

    (New in version 1.4) Specify a parameter for the form calling the function, e.g. with
    ``angiogenic_factor_form(af, af0, c, v, parameters, alpha_T=10)``. If both a Parameters object and a
    parameter as input are given, the function will choose the input parameter.

    :param af: angiogenic factor field
    :param af_0: initial condition for the angiogenic factor field
    :param c: capillaries field
    :param v: test function for the equation
    :param parameters: simulation parameters
    :return:
    """
    # get parameters
    alfa, D, dt = _unpack_parameters_list(["alpha_T", "D", "dt"],
                                          parameters,
                                          kwargs)
    # define reaction term
    reaction_term = alfa * af * c
    reaction_term_non_negative = fenics.conditional(fenics.gt(reaction_term, fenics.Constant(0.0)),
                                                    reaction_term,
                                                    fenics.Constant(0.))
    reaction_term_form = reaction_term_non_negative * v * fenics.dx
    # define time discretization
    time_discretization = ((af - af_0) / dt) * v * fenics.dx
    # define diffusion
    diffusion = D * fenics.dot(fenics.grad(af), fenics.grad(v)) * fenics.dx
    # add terms
    F = time_discretization + diffusion + reaction_term_form

    return F
