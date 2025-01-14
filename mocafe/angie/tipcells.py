"""
This module contains classes and methods to manage the tip cells in Mocafe. More precisely, it provides useful
tools to activate, remove, and move the tip cell in the spatial domain.

If you use this model in your research, remember to cite the original paper describing the model:

    Travasso, R. D. M., Poiré, E. C., Castro, M., Rodrguez-Manzaneque, J. C., & Hernández-Machado, A. (2011).
    Tumor angiogenesis and vascular patterning: A mathematical model. PLoS ONE, 6(5), e19989.
    https://doi.org/10.1371/journal.pone.0019989

For a use example see the :ref:`Angiogenesis <Angiogenesis 2D Demo>` and the
:ref:`Angiogenesis 3D <Angiogenesis 2D Demo>` demos.
"""

import fenics
import numpy as np
from typing import List
import random
import logging
import json
import mocafe.fenut.fenut as fu
from mocafe.angie.base_classes import BaseCell, ClockChecker
from mocafe.fenut.parameters import Parameters, _unpack_parameter
from mocafe.fenut.log import InfoCsvAdapter, DebugAdapter

# get _rank
_comm = fenics.MPI.comm_world
_rank = _comm.Get_rank()
_size = _comm.Get_size()

# configure _logger
_logger = logging.getLogger(__name__)
_info_adapter = InfoCsvAdapter(_logger, {"_rank": _rank, "module": __name__})
_debug_adapter = DebugAdapter(_logger, {"_rank": _rank, "module": __name__})


class TipCell(BaseCell):
    """
    Class representing a tip cell. The tip cells are represented as a circle with a given radius.
    """
    def __init__(self, position: np.ndarray, radius, creation_step):
        """
        inits a TipCell in the given position for the given radius.

        :param position: tip cell position
        :param radius: tip cell radius
        :param creation_step: the simulation step when the tip cell have been created. It is used for internal purposes.
        """
        super(TipCell, self).__init__(position, creation_step)
        self.radius = radius

    def move(self, new_position):
        """
        Move the tip cell to the new position.

        :param new_position: the new position where to move the tip cell.
        :return: nothing
        """
        self.position = new_position

    def get_radius(self):
        """
        Get the radius of the tip cell

        :return: the radius of the tip cell
        """
        return self.radius

    def is_point_inside(self, x):
        """
        Check if the given point is inside the tip cell

        :param x: point to check
        :return: True if the point is inside; False otherwise
        """
        return self.get_distance(x) <= self.radius


class TipCellsField(fenics.UserExpression):
    r"""
    Expression representing the capillary field value inside the tip cells.

    In this implementation, the value is coherent with the one used by Travasso et al (2011) in their Phase Field
    angiogenesis model :cite:`Travasso2011a`, that is:

    .. math::
       \frac{\alpha_p(af) \cdot \pi \cdot R_c}{2 \cdot |v|}

    Where :math:`R_c` is the radius of the tip cell, :math:`v` is the velocity of the tip cell, and
    :math:`\alpha_p(af)` is the proliferation rate for the capillaries' cells, defined as a function of the angiogenic
    factor concentration (:math:`af`) which reads:

    .. math::
       \alpha_p(af) &= \alpha_p \cdot af_p \quad \textrm{if} \quad af>af_p \\
                    &= \alpha_p \cdot af  \quad \textrm{if} \quad 0<af \le af_p \\
                    & = 0 \quad \textrm{if} \quad af \le 0

    """
    def __floordiv__(self, other):
        pass

    def __init__(self, mesh_dim: int = None, parameters: Parameters = None, **kwargs):
        """
        inits the TipCellField for the given simulation parameters

        :param parameters: simulation parameters
        """
        super(TipCellsField, self).__init__()
        self.alpha_p = _unpack_parameter("alpha_p", parameters, kwargs)
        self.T_p = _unpack_parameter("T_p", parameters, kwargs)
        self.phi_min = _unpack_parameter("phi_min", parameters, kwargs)
        self.phi_max = _unpack_parameter("phi_max", parameters, kwargs)
        self.tip_cells_positions = []
        self.tip_cells_radiuses = np.array([])
        self.velocity_norms = np.array([])
        self.T_values = np.array([])
        if mesh_dim is not None:
            self.phi_c_dimensionality_constant = (np.pi / 2) if mesh_dim == 2 else (4. / 3.)
        else:
            raise RuntimeError("Mesh dim not defined")

    def add_tip_cell(self, tip_cell: TipCell, velocity, af_at_point):
        """
        Add a tip cell to the field.

        :param tip_cell: the tip cell to add.
        :param velocity: the velocity of the tip cell, that is used for computing the field value.
        :param af_at_point: the angiogenic factor concentration at the tip cell center, that is used for computing the
            field value.
        :return:
        """
        self.tip_cells_positions.append(tip_cell.get_position())
        self.tip_cells_radiuses = np.append(self.tip_cells_radiuses, tip_cell.get_radius())
        self.velocity_norms = np.append(self.velocity_norms, np.linalg.norm(velocity))
        self.T_values = np.append(self.T_values, self.T_p if af_at_point > self.T_p else af_at_point)

    def compute_phi_c(self, T_value, radius, velocity_norm):
        r"""
        Compute the value of a point inside the tip cell inside the eval method. According to :cite:`Travasso2011a`,
        the value in 2D is:

        .. math::
            \phi_c = \frac{\pi}{2}\frac{\alpha_p \cdot af \cdot r}{|v|}

        In 3D the value is slightly different, since tip cells are spheres and not circles:

        .. math::
            \phi_c = \frac{4}{3}\frac{\alpha_p \cdot af \cdot r}{|v|}

        :param T_value: af value
        :param radius: radius of the tip cell
        :param velocity_norm: norm of the velocity vector
        """
        return self.phi_c_dimensionality_constant * ((self.alpha_p * T_value * radius) / velocity_norm)

    def eval(self, values, x):
        """
        evaluate the field value for the given point

        :param values: internal FEniCS parameter
        :param x: given point
        :return: nothing
        """
        point_value = self.phi_min
        if self.tip_cells_positions:
            try:
                is_inside_array = np.sum((x - self.tip_cells_positions) ** 2, axis=1) <= (self.tip_cells_radiuses ** 2)
            except ValueError:
                raise ValueError(f"Found error with the following params: \n"
                                 f"* {self.tip_cells_positions} \n"
                                 f"* {x} \n"
                                 f"* {self.tip_cells_radiuses} \n")
            if any(is_inside_array):
                radius = self.tip_cells_radiuses[is_inside_array]
                velocity_norm = self.velocity_norms[is_inside_array]
                T_value = self.T_values[is_inside_array]
                phi_c = self.compute_phi_c(T_value, radius, velocity_norm)
                point_value = np.max(phi_c)
        values[0] = point_value

    def value_shape(self):
        return ()


class TipCellManager:
    """
    Class to manage the tip cells throughout the simulation.
    """
    def __init__(self, mesh: fenics.Mesh,
                 parameters: Parameters = None,
                 initial_tcs: List[TipCell] = None,
                 **kwargs):
        """
        inits a TipCellManager

        :param mesh: mesh
        :param parameters: simulation parameters
        :param initial_tcs: set a list of tip cells as initial tip cell list for the TipCellManager. Default is None,
            which sets the initial tip cell list to an empty list.
        """
        self.mesh = mesh
        mesh.bounding_box_tree()  # done for MPI; otherwise idle (bounding box must be built on all processes)
        self.parameters = parameters
        self.kwargs = kwargs
        self.T_c = _unpack_parameter("T_c", parameters, kwargs)
        self.G_m = _unpack_parameter("G_m", parameters, kwargs)
        self.phi_th = _unpack_parameter("phi_th", parameters, kwargs)
        self.cell_radius = _unpack_parameter("R_c", parameters, kwargs)
        self.G_M = _unpack_parameter("G_M", parameters, kwargs)
        self.alpha_p = _unpack_parameter("alpha_p", parameters, kwargs)
        self.T_p = _unpack_parameter("T_p", parameters, kwargs)
        self.chi = _unpack_parameter("chi", parameters, kwargs)
        self.dt = _unpack_parameter("dt", parameters, kwargs)
        self.min_tipcell_distance = _unpack_parameter("min_tipcell_distance", parameters, kwargs)
        self.clock_checker = ClockChecker(mesh, self.cell_radius, start_point="west")
        self.local_box = self._build_local_box(self.cell_radius)
        self.global_tip_cells_list = []
        self.local_tip_cells_list = []
        self.latest_t_c_f_function = None
        if initial_tcs is None:
            pass
        else:
            for tc in initial_tcs:
                self._add_tip_cell(tc)
        self.incremental_tip_cell_file = None

    def get_global_tip_cells_list(self):
        """
        Get the global tip cell list, i.e. all the tip cells for all the MPI processes

        :return: a list of the tip cells
        """
        return self.global_tip_cells_list

    def _point_distant_to_tip_cells(self, point: fenics.Point):
        """
        INTERNAL USE.
        Check if the given point is distant from all the tip cells. The point is "distant" if the distance between
        the given point and the closest tip cell is bigger than the parameter "min_tipcell_distance", that must be
        defined inside the simulation parameters.

        :param point: the point to check
        :return: True if exists at least one tip cell that is "close" to the point; False otherwise.
        """
        if self.global_tip_cells_list:
            for tip_cell in self.global_tip_cells_list:
                if point.distance(fenics.Point(tip_cell.get_position())) < self.min_tipcell_distance:
                    return False
        return True

    def _build_local_box(self, cell_radius):
        """
        INTERNAL USE.
        Builds the local box for the current MPI process. The local box is used by the TipCellManager to build the
        local tip cell list, which is the list of the tip cells the current MPI process "knows".

        :param cell_radius: the tip cell radius, which is used to build the local box
        :return:
        """
        return fu.build_local_box(self.mesh, cell_radius)

    def _is_in_local_box(self, position):
        """
        INTERNAL USE.
        Check if the given position is inside the current MPI process local box

        :param position: the position to check
        :return: True if the position is inside the local box; False otherwise.
        """
        return fu.is_in_local_box(self.local_box, position)

    def _add_tip_cell(self, tip_cell: TipCell):
        """
        INTERNAL USE.
        Add the given tip cell to the list of tip cells that the TipCellManager manages. The tip cell is added both to
        the global tip cells list and to the local tip cells list.

        :param tip_cell: the tip cell to add
        :return: nothing
        """
        # check if the tip cell to add it the same on all processes
        if _size > 1:
            # gather tcs to be added
            tc_on_processes = _comm.gather(tip_cell, root=0)
            # check if are all equal
            if _rank == 0:
                are_tc_equal = [tc == tip_cell for tc in tc_on_processes]
                are_tc_all_equal = all(are_tc_equal)
                error_msg = ""
                for index, test_result in enumerate(are_tc_equal):
                    if test_result:
                        pass
                    else:
                        error_msg += f"Tip Cell on p{index} is different from Tip Cell on p0 \n"
            else:
                are_tc_all_equal = None
                error_msg = None
            are_tc_all_equal = _comm.bcast(are_tc_all_equal, root=0)
            if are_tc_all_equal:
                pass
            else:
                error_msg = _comm.bcast(error_msg, root=0)
                error_msg = "Can't add different Tip Cells on different MPI processes. \n" + error_msg
                raise RuntimeError(error_msg)

        # add tip cell
        self.global_tip_cells_list.append(tip_cell)
        if self._is_in_local_box(tip_cell.get_position()):
            self.local_tip_cells_list.append(tip_cell)

    def activate_tip_cell(self, c, af, grad_af, current_step):
        """
        Activates a tip cell if the right conditions on the capillaries field c, the angiogenic factor field af and
        its gradient, grad_af, are met.

        In this implementation the conditions are coherent with the one used by Travasso et al. (2011)
        :cite:`Travasso2011a`, which are reported in the following pseudo-code::

            p = possible new tip cell center
            if distance(p, closest_tip_cell) > min_tipcell_distance:
                if c(p) > phi_th:
                    if af(p) > T_c:
                        if norm(grad_af(c)) > G_m
                            create new tip cell at point p
            else:
                do nothing

        Where ``min_tipcell_distance``, ``phi_th``, ``T_c``, and ``G_m`` are defined in the simulation parameters.

        The procedure above is applied to every point of the mesh.

        If more than two point are found as possible new tip cell positions, only one is randomly selected. Thus, in
        this implementation only one tip cell can be activated at each call of the method.

        :param c: capillaries field
        :param af: angiogenic factor field
        :param grad_af: gradient of the angiogenic factor field
        :param current_step: current simulation step. it is used for internal purpose
        :return:
        """
        # define root _rank
        root = 0
        # logging
        _info_adapter.info(f"Called {self.activate_tip_cell.__name__}")
        # get local mesh points
        local_mesh_points = self.mesh.coordinates()
        # initialize local possible locations list
        local_possible_locations = []
        # Debug: setup cunters to check which test is not passed
        _debug_adapter.debug(f"Searching for new tip cells")
        n_points_to_check = len(local_mesh_points)
        n_points_distant = 0
        n_points_phi_09 = 0
        n_points_over_Tc = 0
        n_points_over_Gm = 0
        n_points_distant_to_edge = 0
        for point in local_mesh_points:
            if self._point_distant_to_tip_cells(fenics.Point(point)):
                n_points_distant += 1
                if c(point) > self.phi_th:
                    n_points_phi_09 += 1
                    if af(point) > self.T_c:
                        n_points_over_Tc += 1
                        if np.linalg.norm(grad_af(point)) > self.G_m:
                            n_points_over_Gm += 1
                            if not self.clock_checker.clock_check(point, c, -self.phi_th,
                                                                  lambda value, thr: value < thr):
                                n_points_distant_to_edge += 1
                                local_possible_locations.append(point)
        debug_msg = \
            f"Finished checking. I found: \n" \
            f"\t* {n_points_distant} / {n_points_to_check} distant to the current tip cells \n" \
            f"\t* {n_points_phi_09} / {n_points_to_check} which were at phi > {self.phi_th} \n" \
            f"\t* {n_points_over_Tc} / {n_points_to_check} which were at T > {self.T_c} \n" \
            f"\t* {n_points_over_Gm} / {n_points_to_check} which were at G > {self.G_m} \n" \
            f"\t* {n_points_over_Gm} / {n_points_to_check} new possible locations"
        for line in debug_msg.split("\n"):
            _debug_adapter.debug(line)

        # gather possible locations on root
        local_possible_locations_lists = _comm.gather(local_possible_locations, root)

        # pick new cell position on root
        if _rank == root:
            possible_locations = [item for sublist in local_possible_locations_lists for item in sublist]
            # get one, if there is a possible location
            if possible_locations:
                new_tip_cell_position = random.choice(possible_locations)
            else:
                new_tip_cell_position = None
        else:
            new_tip_cell_position = None

        # broadcast new tip cell position
        new_tip_cell_position = _comm.bcast(new_tip_cell_position, root)

        # create tip cell and add it to the list
        if new_tip_cell_position is not None:
            new_tip_cell = TipCell(new_tip_cell_position,
                                   self.cell_radius,
                                   current_step)
            self._add_tip_cell(new_tip_cell)
            _debug_adapter.debug(f"Created new tip cell at point {new_tip_cell_position}")

    def _remove_tip_cells(self, local_to_remove):
        """
        INTERNAL USE.
        Remove the tip cells in the given list from both the global and local tip cell list.

        :param local_to_remove: list of tip cells to remove
        :return: nothing
        """
        # define root _rank
        root = 0
        # get global to remove list
        local_to_remove_array = _comm.gather(local_to_remove, root)
        if _rank == root:
            global_to_remove = fu.flatten_list_of_lists(local_to_remove_array)
            # remove duplicates
            global_to_remove = list(set(global_to_remove))
        else:
            global_to_remove = None
        global_to_remove = _comm.bcast(global_to_remove, root)
        _debug_adapter.debug(f"Created global_to_remove list. It includes:")
        for tip_cell in global_to_remove:
            _debug_adapter.debug(f"\t* tip_cell at position {tip_cell.get_position()}")

        # remove cells from global and local
        for tip_cell in global_to_remove:
            _debug_adapter.debug(f"Removing tip cell at position {tip_cell.get_position()}")
            self.global_tip_cells_list.remove(tip_cell)
            if tip_cell in self.local_tip_cells_list:
                self.local_tip_cells_list.remove(tip_cell)

    def revert_tip_cells(self, af, grad_af):
        """
        Deactivate the tip cells when the right conditions are met.

        In this implementation the conditions are coherent with the one used by Travasso et al. (2011)
        :cite:`Travasso2011a`, which are reported in the following pseudo-code::

            tc_p = a tip cell position
            if (af(tc_p) < T_c or norm(grad_af(tc_p)) < G_m):
                deactivate tip cell at position tc_p
            else:
                do nothing

        Where ``T_c`` and ``G_m`` are constants defined in the simulation parameter.

        The procedure above is applied to all the active tip cells.

        *New*: now the tip cells are deactivated also if there are other Tip Cells nearer then the distance
        contained in the parameter 'min_tipcell_distance'. This was introduced to simulate the effect of Delta-
        Notch signalling also on active Tip Cells, which was not present in Travasso et al. (2011) :cite:`Travasso2011a`
        but has been introduced by Moreira-Soares et al. (2018) :cite:`MoreiraSoares2018`.

        :param af: angiogenic factor field
        :param grad_af: gradient of the angiogenic factor
        :return: nothing
        """
        _info_adapter.info(f"Called {self.revert_tip_cells.__name__}")
        # init lists
        local_to_remove = []
        local_to_check_if_outside_global_mesh = []

        """1. For each local tip cell, check if the activation conditions are still met."""
        for tip_cell in self.local_tip_cells_list:
            position = tip_cell.get_position()
            # check if tip cell is inside local mesh
            if fu.is_point_inside_mesh(self.mesh, position):
                # check if conditions are met
                if (af(position) < self.T_c) or (np.linalg.norm(grad_af(position)) < self.G_m):
                    local_to_remove.append(tip_cell)
            else:
                # else add to the list for checking if in global mesh
                local_to_check_if_outside_global_mesh.append(tip_cell)

        """2. For local tip cells which are outside the local mesh, check if they are outside the global mesh. """
        global_to_check_if_outside_global_mesh = _comm.gather(local_to_check_if_outside_global_mesh, 0)
        if _rank == 0:
            global_to_check_if_outside_global_mesh = fu.flatten_list_of_lists(global_to_check_if_outside_global_mesh)
        global_to_check_if_outside_global_mesh = _comm.bcast(global_to_check_if_outside_global_mesh, 0)
        for tip_cell in global_to_check_if_outside_global_mesh:
            is_inside_local_mesh = fu.is_point_inside_mesh(self.mesh, tip_cell.get_position())
            is_inside_local_mesh_array = _comm.gather(is_inside_local_mesh, 0)
            if _rank == 0:
                is_inside_global_mesh = any(is_inside_local_mesh_array)
            else:
                is_inside_global_mesh = None
            is_inside_global_mesh = _comm.bcast(is_inside_global_mesh, 0)
            if not is_inside_global_mesh:
                local_to_remove.append(tip_cell)

        """3. Remove local tip cells near to each other, due to Delta-Notch signalling."""
        near_tcs_to_remove = []  # init list of cells to remove
        if _rank == 0:
            global_tc_list = self.global_tip_cells_list.copy()  # get a copy of the global tip cells (tc) list
            tc_groups_dict = {}  # init dictionary for tc groups
            random.shuffle(global_tc_list)  # sort the list of tc randomly to ensure casual selection

            for tc in global_tc_list:
                near_tcs = []  # init list of the near tip cells
                other_tcs = global_tc_list.copy()
                other_tcs.remove(tc)  # get a list with the other tcs
                for other_tc in other_tcs:
                    is_tc_near_other_tc = \
                        (tc.get_distance(other_tc.get_position()) < self.min_tipcell_distance)  # check if near
                    if is_tc_near_other_tc:
                        near_tcs.append(other_tc)  # if near, add to list
                tc_groups_dict[tc] = near_tcs  # set list as value for dict with key tc

            # sort groups by len
            tc_groups_dict = \
                {tc: tc_group for tc, tc_group
                 in sorted(tc_groups_dict.items(), key=lambda item: len(item[1]), reverse=True)}

            # iterate until all the groups are empty
            while not all(group_len == 0 for group_len in [len(tc_groups_dict[tc]) for tc in tc_groups_dict]):
                current_tc_largest_group = list(tc_groups_dict.keys())[0]  # get tc with the largest group
                near_tcs_to_remove.append(current_tc_largest_group)  # append it to local to remove
                tc_groups_dict.pop(current_tc_largest_group)  # remove tc entry from tc_groups_dict
                for tc, tc_group in tc_groups_dict.items():
                    if current_tc_largest_group in tc_group:
                        tc_group.remove(current_tc_largest_group)
        else:
            pass

        # get the global near tcs to remove
        near_tcs_to_remove = _comm.bcast(near_tcs_to_remove, 0)
        # add the tcs to remove to local_to_remove
        for tc in near_tcs_to_remove:
            if (tc in self.local_tip_cells_list) and (tc not in local_to_remove):
                local_to_remove.append(tc)

        "4 (final). Remove tip cells added to local_to_remove"
        self._remove_tip_cells(local_to_remove)

    def _update_tip_cell_positions_and_get_field(self, af, grad_af):
        """
        INTERNAL USE.
        Updates the tip cell position according to the angiogenic factor distribution and returns the tip cells field.

        :param af: angiogenic factor field
        :param grad_af: angiogenic factor gradient
        :return: the updated tip cells field
        """
        # init tip cell field
        tip_cells_field_expression = TipCellsField(self.mesh.geometric_dimension(), self.parameters, **self.kwargs)

        # define root _rank
        root = 0
        # initialize cells went out of mesh
        tip_cells_out_of_mesh = []

        # iterate on all tip cells
        for tip_cell in self.global_tip_cells_list:
            # get position
            tip_cell_position = tip_cell.get_position()
            # the process that has access to tip cell position computes the mesh_related values
            if fu.is_point_inside_mesh(self.mesh, tip_cell_position):
                # compute velocity
                velocity = self.compute_tip_cell_velocity(grad_af, self.chi, tip_cell_position)
                # compute value of T in position
                T_at_point = af(tip_cell_position)
            else:
                velocity = None
                T_at_point = None

            # gather valocity and T_at_point
            velocity_array = _comm.gather(velocity, root)
            T_at_point_array = _comm.gather(T_at_point, root)
            if _rank == root:
                # remove nones
                velocity_array_no_nones = [v for v in velocity_array
                                           if v is not None]
                T_at_point_array_no_nones = [val for val in T_at_point_array
                                             if val is not None]
                # get velocity
                velocity = velocity_array_no_nones[0]
                # get T_value
                T_at_point = T_at_point_array_no_nones[0]
            else:
                velocity = None
                T_at_point = None
            # bcast velocity and T_at_point
            velocity = _comm.bcast(velocity, root)
            T_at_point = _comm.bcast(T_at_point, root)

            # compute new position
            new_position = tip_cell_position + (self.dt * velocity)
            debug_msg = \
                f"DEBUG: p{fenics.MPI.comm_world.Get_rank()}: computing new tip cell position: \n" \
                f"\t*[tip cell position] + [dt] * [velocity] = \n" \
                f"\t*{tip_cell_position} + {self.dt} * {velocity} = {new_position}"
            for line in debug_msg.split("\n"):
                _debug_adapter.debug(line)

            # check if new position is local mesh
            is_new_position_in_local_mesh = fu.is_point_inside_mesh(self.mesh, new_position)
            # check if new position is in global mesh
            is_new_position_in_local_mesh_array = _comm.gather(is_new_position_in_local_mesh, 0)
            if _rank == 0:
                is_new_position_in_global_mesh = any(is_new_position_in_local_mesh_array)
            else:
                is_new_position_in_global_mesh = None
            is_new_position_in_global_mesh = _comm.bcast(is_new_position_in_global_mesh, 0)

            # if new position is not in global mesh
            if not is_new_position_in_global_mesh:
                tip_cells_out_of_mesh.append(tip_cell)  # set cell as to remove
            else:
                # else update local lists
                if tip_cell in self.local_tip_cells_list:
                    if not self._is_in_local_box(new_position):  # if tip cell is no more in the local box
                        self.local_tip_cells_list.remove(tip_cell)  # remove it
                else:
                    if self._is_in_local_box(new_position):  # if tip cell is now in the local box
                        self.local_tip_cells_list.append(tip_cell)  # append it

            # move tip cell
            tip_cell.move(new_position)

            # append everything to tip_cell_field
            tip_cells_field_expression.add_tip_cell(tip_cell, velocity, T_at_point)

        # remove tip cells went out of mesh
        self._remove_tip_cells(tip_cells_out_of_mesh)

        # return tip cells field
        return tip_cells_field_expression

    def _assign_values_to_vector(self, c, t_c_f_function):
        """
        Assign the positive values of ``t_c_f_function`` to the capillaries field c.

        :param c: capillaries field
        :param t_c_f_function: tip cell field function
        :return: nothing
        """
        # get local values for T and source_field
        t_c_f_loc_values = t_c_f_function.vector().get_local()
        phi_loc_values = c.vector().get_local()
        # set T to 1. where source_field is 1
        where_t_c_f_greater_than_0 = t_c_f_loc_values > 0.
        phi_loc_values[where_t_c_f_greater_than_0] = t_c_f_loc_values[where_t_c_f_greater_than_0]
        c.vector().set_local(phi_loc_values)
        c.vector().update_ghost_values()  # necessary, otherwise errors

    def _apply_tip_cells_field(self, c, tip_cells_field_expression):
        """
        INTERNAL USE.
        Applies the tip cells field in the given ``tip_cells_field_expression`` to the capillaries field ``c``.

        More precisely, all the values in the tip cell field greater than zero are pasted over the the capillaries
        field.

        :param c: the capillaries field
        :param tip_cells_field_expression: the tip cells field expression
        :return: the tip cell field as a FEniCS function
        """
        # get Function Space of af
        V_c = c.function_space()

        # check if V_c is sub space
        try:
            V_c.collapse()
            is_V_sub_space = True
        except RuntimeError:
            is_V_sub_space = False

        if not is_V_sub_space:
            # interpolate tip_cells_field
            t_c_f_function = fenics.interpolate(tip_cells_field_expression, V_c)
            # assign t_c_f_function to c where is greater than 0
            self._assign_values_to_vector(c, t_c_f_function)
        else:
            # collapse subspace
            V_collapsed = V_c.collapse()
            # interpolate tip cells field
            t_c_f_function = fenics.interpolate(tip_cells_field_expression, V_collapsed)
            # create assigner to collapsed
            assigner_to_collapsed = fenics.FunctionAssigner(V_collapsed, V_c)
            # assign c to local variable phi_temp
            phi_temp = fenics.Function(V_collapsed)
            assigner_to_collapsed.assign(phi_temp, c)
            # assign values to phi_temp
            self._assign_values_to_vector(phi_temp, t_c_f_function)
            # create inverse assigner
            assigner_to_sub = fenics.FunctionAssigner(V_c, V_collapsed)
            # assign phi_temp to c
            assigner_to_sub.assign(c, phi_temp)

        # return tip cells field function for monitoring
        return t_c_f_function

    def move_tip_cells(self, c, af, grad_af):
        r"""
        Move the tip cell to follow the gradient of the angiogenic factor, with the velocity computed by the method
        ``compute_tip_cell_velocity``.

        The method also updates the tip cell field and returns it.

        The tip cells field is a FEniCS function which inside each tip cell has the value defined by Travasso et al.
        (2011) :cite:`Travasso2011a`, which is:

        .. math::
           \frac{\alpha_p(af) \cdot \pi \cdot R_c}{2 \cdot |v|}

        In every other point, the function has value 0.

        :param c: capillaries field
        :param af: angiogenic factor field
        :param grad_af: gradient of the angiogenic factor field
        :return:
        """
        _info_adapter.info(f"Called {self.move_tip_cells.__name__}")
        # update tip cell positions
        tip_cells_field_expression = self._update_tip_cell_positions_and_get_field(af, grad_af)
        # apply tip_cells_field to c
        self.latest_t_c_f_function = self._apply_tip_cells_field(c, tip_cells_field_expression)

    def compute_tip_cell_velocity(self, grad_af, chi, tip_cell_position):
        r"""
        Compute the tip cell velocity given its position, the gradient of the angiogenic factor, and the constant chi.

        In this implementation the velocity is computed according to the model presented by Travasso et al. (2011)
        :cite:`Travasso2011a`. The formula is:

        .. math::
           v = \chi \nabla af [1 + (\frac{G_M}{G})\cdot (G - G_M)]

        Where :math:`G` is the norm of the angiogenic factor gradient (:math:`\nabla af`).

        :param grad_af:
        :param chi:
        :param tip_cell_position:
        :return:
        """
        grad_T_at_point = grad_af(tip_cell_position)
        G_at_point = np.linalg.norm(grad_T_at_point)
        if G_at_point < self.G_M:
            velocity = chi * grad_T_at_point
        else:
            velocity = chi * grad_T_at_point * (self.G_M / G_at_point)

        return velocity

    def get_latest_tip_cell_function(self):
        if self.latest_t_c_f_function is None:
            raise RuntimeError("Tip cell function has not have been computed yet")
        else:
            return self.latest_t_c_f_function

    def _make_tip_cells_dict(self):
        """
        INTERNAL USE

        Creates a dictionary with the current tip cells data. Used for creating tip cells json objects
        """
        tc_dict = {}
        for tc in self.global_tip_cells_list:
            tc_dict[f"tc{hash(tc)}"] = {
                "position": tc.position.tolist(),
                "radius": tc.radius,
                "creation step": tc.creation_step
            }
        return tc_dict

    def save_tip_cells(self, tc_file: str):
        """
        Stores the current global tip cell list in a readable json file.

        :param tc_file: file where to store the json tip cell list.
        """
        # check if input file is json file
        if tc_file.endswith(".json"):
            pass
        else:
            raise RuntimeError("Input file must be a json file.")

        if _rank == 0:
            # create dict from global tc list
            tc_dict = self._make_tip_cells_dict()

            # save to file
            with open(tc_file, "w") as outfile:
                json.dump(tc_dict, outfile)

        # wait for all the processes
        _comm.Barrier()

    def save_incremental_tip_cells(self, tc_file: str, step: int):
        """
        Stores the global tip cell list in a readable json file at every time step.

        :param tc_file: file where to store the json tip cell list.
        :param step: time step
        """
        # check if input file is json file
        if tc_file.endswith(".json"):
            pass
        else:
            raise RuntimeError("Input file must be a json file.")
        # check if this method has been called for the first time
        first_time_called = self.incremental_tip_cell_file is None
        # set file name
        if first_time_called:
            self.incremental_tip_cell_file = tc_file
        if _rank == 0:
            # init dict
            if first_time_called:
                incremental_tc_dict = {}
            else:
                with open(self.incremental_tip_cell_file) as infile:
                    incremental_tc_dict = json.load(infile)

            # create dict from global tc list
            incremental_tc_dict[f"step_{step}"] = self._make_tip_cells_dict()

            # save to file
            with open(self.incremental_tip_cell_file, "w") as outfile:
                json.dump(incremental_tc_dict, outfile)

        # wait for all the processes
        _comm.Barrier()


def load_tip_cells_from_json(json_file: str):
    """
    Creates a tip cell list from a json file with tip cells data.

    :param json_file: file to load as tip cell list.
    """
    # check if input file is json file
    if json_file.endswith(".json"):
        pass
    else:
        raise RuntimeError("Input file must be a json file.")
    # load json
    with open(json_file) as infile:
        tc_dict = json.load(infile)
    # create tip cells
    tc_list = []
    for tc_entry in tc_dict:
        tc_list.append(
            TipCell(np.array(tc_dict[tc_entry]["position"]),
                    tc_dict[tc_entry]["radius"],
                    tc_dict[tc_entry]["creation step"])
        )
    return tc_list
