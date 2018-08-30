from config import *
from molecule_spec_sutils import *  # import molecule specific unitity code
from coordinates_data_files_list import *
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from keras.models import Sequential, Model, load_model
from keras.optimizers import *
from keras.layers import Dense, Activation, Lambda, Reshape, Input
from keras.regularizers import l2
from keras.callbacks import EarlyStopping
from keras import layers
from keras import backend as K
# import torch
# from torch.autograd import Variable
# import torch.nn as nn
# import torch.nn.functional as F
import random
from compatible import *

##################    set types of molecules  ############################

molecule_type = Sutils.create_subclass_instance_using_name(CONFIG_30)

##########################################################################


class autoencoder(object):
    """the neural network for simulation
    this class includes abstract methods, that must be implemented by subclasses
    """
    def __init__(self,
                 index,  # the index of the current network
                 data_set_for_training,
                 output_data_set = None,  # output data may not be the same with the input data
                 autoencoder_info_file=None,  # this might be expressions, or coefficients
                 training_data_interval=CONFIG_2,
                 hidden_layers_types=CONFIG_17,
                 out_layer_type=CONFIG_78,  # different layers
                 node_num=CONFIG_3,  # the structure of ANN
                 epochs=CONFIG_5,
                 filename_to_save_network=CONFIG_6,
                 hierarchical=CONFIG_44,
                 hi_variant=CONFIG_77,
                 *args, **kwargs  # for extra init functions for subclasses
                 ):

        self._index = index
        self._data_set = data_set_for_training
        self._output_data_set = output_data_set
        self._training_data_interval = training_data_interval
        if autoencoder_info_file is None:
            self._autoencoder_info_file = "../resources/%s/autoencoder_info_%d.txt" % (CONFIG_30, index)
        else:
            self._autoencoder_info_file = autoencoder_info_file
        self._hidden_layers_type = hidden_layers_types
        self._out_layer_type = out_layer_type
        self._node_num = node_num
        self._epochs = epochs
        if filename_to_save_network is None:
            self._filename_to_save_network = "../resources/%s/network_%s.pkl" % (
            CONFIG_30, str(self._index))  # by default naming with its index
        else:
            self._filename_to_save_network = filename_to_save_network

        self._hierarchical = hierarchical
        self._hi_variant = hi_variant
        self._connection_between_layers_coeffs = None
        self._connection_with_bias_layers_coeffs = None
        self._molecule_net_layers = self._molecule_net = self._encoder_net = self._decoder_net = None
        self._init_extra(*args, **kwargs)
        return

    @abc.abstractmethod
    def _init_extra(self):
        """must be implemented by subclasses"""
        pass

    @staticmethod
    def load_from_pkl_file(filename):
        a = Sutils.load_object_from_pkl_file(filename)
        if os.path.isfile(filename.replace('.pkl','.hdf5')):
            a._molecule_net = load_model(filename.replace('.pkl','.hdf5'),custom_objects={'mse_weighted': get_mse_weighted()})
        elif not hasattr(a, '_molecule_net') and hasattr(a, '_molecule_net_layers') and (not a._molecule_net_layers is None):  # for backward compatibility
            a._molecule_net = Sequential()
            for item in a._molecule_net_layers:
                a._molecule_net.add(item)
        else:
            raise Exception('cannot load attribute _molecule_net')
        if os.path.isfile(filename.replace('.pkl', '_encoder.hdf5')):
            a._encoder_net = load_model(filename.replace('.pkl', '_encoder.hdf5'),custom_objects={'mse_weighted': get_mse_weighted()})
        else:
            raise Exception('TODO: construct encoder from _molecule_net') # TODO
        return a
    
    def remove_pybrain_dependency(self):    
        """previously pybrain layers are directly used in attributes of this object, should be replaced by string to remove dependency"""
        self._in_layer_type = None
        self._hidden_layers_type = [layer_type_to_name_mapping[item] for item in self._hidden_layers_type]
        self._out_layer_type = layer_type_to_name_mapping[self._out_layer_type]
        return

    @staticmethod
    def remove_pybrain_dependency_and_save_to_file(filename):
        ae = autoencoder.load_from_pkl_file(filename)
        ae.remove_pybrain_dependency()
        ae.save_into_file(filename)
        return

    def save_into_file(self, filename=CONFIG_6, fraction_of_data_to_be_saved = 1.0):
        if filename is None:
            filename = self._filename_to_save_network

        if fraction_of_data_to_be_saved != 1.0:
            number_of_data_points_to_be_saved = int(self._data_set.shape[0] * fraction_of_data_to_be_saved)
            print(("Warning: only %f of data (%d out of %d) are saved into pkl file" % (fraction_of_data_to_be_saved,
                                                                                        number_of_data_points_to_be_saved,
                                                                                        self._data_set.shape[0])))
            self._data_set = self._data_set[:number_of_data_points_to_be_saved]
            if not self._output_data_set is None:        # for backward compatibility
                self._output_data_set = self._output_data_set[:number_of_data_points_to_be_saved]

        hdf5_file_name = filename.replace('.pkl', '.hdf5')
        hdf5_file_name_encoder = hdf5_file_name.replace('.hdf5', '_encoder.hdf5')
        hdf5_file_name_decoder = hdf5_file_name.replace('.hdf5', '_decoder.hdf5')
        for item_filename in [filename, hdf5_file_name, hdf5_file_name_encoder, hdf5_file_name_decoder]:
            Helper_func.backup_rename_file_if_exists(item_filename)
        folder_to_store_files = os.path.dirname(filename)
        if folder_to_store_files != '' and (not os.path.exists(folder_to_store_files)):
            subprocess.check_output(['mkdir', '-p', folder_to_store_files])
        self._molecule_net.save(hdf5_file_name)
        self._encoder_net.save(hdf5_file_name_encoder)
        if not self._decoder_net is None: self._decoder_net.save(hdf5_file_name_decoder)
        self._molecule_net = self._molecule_net_layers = self._encoder_net = self._decoder_net = None  # we save model in hdf5, not in pkl
        with open(filename, 'wb') as my_file:
            pickle.dump(self, my_file, pickle.HIGHEST_PROTOCOL)

        self._molecule_net = load_model(hdf5_file_name, custom_objects={'mse_weighted': get_mse_weighted()})
        self._encoder_net = load_model(hdf5_file_name_encoder, custom_objects={'mse_weighted': get_mse_weighted()})
        # self._decoder_net = load_model(hdf5_file_name_decoder, custom_objects={'mse_weighted': mse_weighted})
        return

    def get_expression_script_for_plumed(self, mode="native", node_num=None, connection_between_layers_coeffs=None,
                                         connection_with_bias_layers_coeffs=None, index_CV_layer=None,
                                         activation_function_list=None):
        if node_num is None: node_num = self._node_num
        if connection_between_layers_coeffs is None: connection_between_layers_coeffs = self._connection_between_layers_coeffs
        if connection_with_bias_layers_coeffs is None: connection_with_bias_layers_coeffs = self._connection_with_bias_layers_coeffs
        if index_CV_layer is None: index_CV_layer = (len(node_num) - 1) / 2
        plumed_script = ''
        if mode == "native":  # using native implementation by PLUMED (using COMBINE and MATHEVAL)
            plumed_script += "bias_const: CONSTANT VALUE=1.0\n"  # used for bias
            if activation_function_list is None: activation_function_list = ['tanh'] * index_CV_layer
            for layer_index in range(1, index_CV_layer + 1):
                for item in range(node_num[layer_index]):
                    plumed_script += "l_%d_in_%d: COMBINE PERIODIC=NO COEFFICIENTS=" % (layer_index, item)
                    plumed_script += "%s" % \
                                     str(connection_between_layers_coeffs[layer_index - 1][
                                         item * node_num[layer_index - 1]:(item + 1) * node_num[
                                             layer_index - 1]].tolist())[1:-1].replace(' ', '')
                    plumed_script += ',%f' % connection_with_bias_layers_coeffs[layer_index - 1][item]
                    plumed_script += " ARG="
                    for _1 in range(node_num[layer_index - 1]):
                        plumed_script += 'l_%d_out_%d,' % (layer_index - 1, _1)

                    plumed_script += 'bias_const\n'

                if activation_function_list[layer_index - 1] == 'tanh':
                    for item in range(node_num[layer_index]):
                        plumed_script += 'l_%d_out_%d: MATHEVAL ARG=l_%d_in_%d FUNC=tanh(x) PERIODIC=NO\n' % (
                            layer_index, item, layer_index,item)
                elif activation_function_list[layer_index - 1] == 'softmax':    # generalization for classifier
                    plumed_script += "sum_output_layer: MATHEVAL ARG="
                    for item in range(node_num[layer_index]): plumed_script += 'l_%d_in_%d,' % (layer_index, item)
                    plumed_script = plumed_script[:-1]  + ' VAR='                 # remove last ','
                    for item in range(node_num[layer_index]): plumed_script += 't_var_%d,' % item
                    plumed_script = plumed_script[:-1] + ' FUNC='
                    for item in range(node_num[layer_index]): plumed_script += 'exp(t_var_%d)+' % item
                    plumed_script = plumed_script[:-1] + ' PERIODIC=NO\n'
                    for item in range(node_num[layer_index]):
                        plumed_script += 'l_%d_out_%d: MATHEVAL ARG=l_%d_in_%d,sum_output_layer FUNC=exp(x)/y PERIODIC=NO\n' % (
                            layer_index, item, layer_index, item)
        elif mode == "ANN":  # using ANN class
            temp_num_of_layers_used = index_CV_layer + 1
            temp_input_string = ','.join(['l_0_out_%d' % item for item in range(node_num[0])])
            temp_num_nodes_string = ','.join([str(item) for item in node_num[:temp_num_of_layers_used]])
            temp_layer_type_string = CONFIG_17[:2]
            temp_layer_type_string = ','.join(temp_layer_type_string)
            temp_coeff_string = ''
            temp_bias_string = ''
            for _1, item_coeff in enumerate(connection_between_layers_coeffs[:temp_num_of_layers_used - 1]):
                temp_coeff_string += ' COEFFICIENTS_OF_CONNECTIONS%d=%s' % \
                                     (_1, ','.join([str(item) for item in item_coeff]))
            for _1, item_bias in enumerate(connection_with_bias_layers_coeffs[:temp_num_of_layers_used - 1]):
                temp_bias_string += ' VALUES_OF_BIASED_NODES%d=%s' % \
                                     (_1, ','.join([str(item) for item in item_bias]))

            plumed_script += "ann_force: ANN ARG=%s NUM_OF_NODES=%s LAYER_TYPES=%s %s %s" % \
                (temp_input_string, temp_num_nodes_string, temp_layer_type_string,
                 temp_coeff_string, temp_bias_string)
        else:
            raise Exception("mode error")
        return plumed_script

    def get_plumed_script_for_biased_simulation_with_INDUS_cg_input_and_ANN(self,
            water_index_string, atom_indices, r_low, r_high, scaling_factor, sigma=0.1, cutoff=0.2,
            potential_center=None, force_constant=None, out_plumed_file=None):
        """ used to generate plumed script for biased simulation, with INDUS coarse grained water
        molecule numbers as input for ANN, and biasing force is applied on outputs of ANN
        :param water_index_string: example: '75-11421:3'
        :param atom_indices: example: range(1, 25)
        :param scaling_factor: scaling factor for input of ANN
        :param sigma, cutoff: these are parameters for Gaussian, in unit of A (by default in plumed it is nanometer)
        :param potential_center: if it is None, does not generate biasing part in script
        """
        return self.get_plumed_script_for_biased_simulation_with_solute_pairwise_dis_and_solvent_cg_input_and_ANN(
            [], 0, water_index_string=water_index_string, solute_atoms_cg=atom_indices,
            r_low=r_low, r_high=r_high, scaling_solvent=scaling_factor, sigma=sigma, cutoff=cutoff,
            potential_center=potential_center, force_constant=force_constant, out_plumed_file=out_plumed_file
        )

    def get_plumed_script_for_biased_simulation_with_solute_pairwise_dis_and_solvent_cg_input_and_ANN(
            self, solute_atom_indices, scaling_solute, water_index_string, solute_atoms_cg, r_low, r_high,
            scaling_solvent, sigma=0.1, cutoff=0.2, potential_center=None, force_constant=None, out_plumed_file=None
    ):
        """ used to generate plumed script for biased simulation, with 1. pairwise distances of solute atoms,
        2. INDUS coarse grained water molecule numbers as input for ANN, and biasing force is applied on outputs of ANN
        :param solute_atom_indices: solute atoms for computing pairwise distances
        :param scaling_solute: scaling factor for solute when computing pairwise distances
        :param water_index_string: example: '75-11421:3', used in plumed script
        :param solute_atoms_cg: solute atoms for computing cg water counts, example: range(1, 25)
        :param scaling_solvent: scaling factor for solvent cg counts
        :param sigma, cutoff: these are parameters for Gaussian, in unit of A (by default in plumed it is nanometer)
        :param potential_center: if it is None, does not generate biasing part in script
        """
        result = ''
        result += Sutils._get_plumed_script_with_pairwise_dis_as_input(solute_atom_indices, scaling_factor=scaling_solute)
        num_pairwise_dis = len(solute_atom_indices) * (len(solute_atom_indices) - 1) / 2
        for _1, item in enumerate(solute_atoms_cg):
            result += "sph_%d: SPHSHMOD ATOMS=%s ATOMREF=%d RLOW=%f RHIGH=%f SIGMA=%.4f CUTOFF=%.4f\n" % (
                _1, water_index_string, item, r_low / 10.0, r_high / 10.0,
                sigma / 10.0, cutoff / 10.0)  # factor of 10.0 is used to convert A to nm
            result += "l_0_out_%d: COMBINE PERIODIC=NO COEFFICIENTS=%f ARG=sph_%d.Ntw\n" % (
                _1 + num_pairwise_dis, 1.0 / scaling_solvent, _1)
        result += self.get_expression_script_for_plumed(mode='ANN')  # add string generated by ANN plumed plugin
        if not potential_center is None:
            arg_string = ','.join(['ann_force.%d' % _2 for _2 in range(len(potential_center))])
            pc_string = ','.join([str(_2) for _2 in potential_center])
            if out_plumed_file is None:
                out_plumed_file = "temp_plumed_out_%s.txt" % pc_string
            kappa_string = ','.join([str(force_constant) for _ in potential_center])
            arg_string_2 = ','.join(['l_0_out_%d' % _2 for _2 in range(len(solute_atoms_cg))])
            result += """\nmypotential: RESTRAINT ARG=%s AT=%s KAPPA=%s
ave: COMBINE PERIODIC=NO ARG=%s

PRINT STRIDE=50 ARG=%s,ave FILE=%s""" % (
                arg_string, pc_string, kappa_string, arg_string_2, arg_string, out_plumed_file
            )
        return result

    def write_expression_script_for_plumed(self, out_file=None, mode="native"):
        if out_file is None: out_file = self._autoencoder_info_file
        expression = self.get_expression_script_for_plumed(mode=mode)
        with open(out_file, 'w') as f_out:
            f_out.write(expression)
        return

    def write_coefficients_of_connections_into_file(self, out_file=None):
        index_CV_layer = (len(self._node_num) - 1) / 2
        if out_file is None: out_file = self._autoencoder_info_file
        with open(out_file, 'w') as f_out:
            for item in range(index_CV_layer):
                f_out.write(str(list(self._connection_between_layers_coeffs[item])))
                f_out.write(',\n')
            for item in range(index_CV_layer):
                f_out.write(str(list(self._connection_with_bias_layers_coeffs[item])))
                f_out.write(',\n')
        return

    def check_PC_consistency(self, another_autoencoder, input_data = None, single_component_pair=None):
        from sklearn import linear_model
        assert (isinstance(another_autoencoder, autoencoder))
        if input_data is None:  input_data = self._data_set
        PCs_1 = self.get_PCs(input_data)
        PCs_2 = another_autoencoder.get_PCs(input_data)
        if not single_component_pair is None:  # in this case, we check consistency of single component of PCs
            PCs_1 = PCs_1[:, [single_component_pair[0]]]
            PCs_2 = PCs_2[:, [single_component_pair[1]]]
            # print PCs_1.shape, PCs_2.shape
        temp_regression = linear_model.LinearRegression().fit(PCs_1, PCs_2)
        predicted_PCs_2 = temp_regression.predict(PCs_1)
        r_value = temp_regression.score(PCs_1, PCs_2)
        return PCs_1, PCs_2, predicted_PCs_2, r_value

    @staticmethod
    def pairwise_PC_consistency_check(autoencoder_list, input_data=None, single_component_pair=None):
        result = [[item_1.check_PC_consistency(item_2, input_data=input_data, single_component_pair=single_component_pair)[3]
                  for item_1 in autoencoder_list] for item_2 in autoencoder_list]
        return np.array(result)

    def get_effective_numbers_of_occupied_bins_in_PC_space(self, input_data, range_of_PC_in_one_dim = [-1, 1],
                                                           num_of_bins=10, min_num_per_bin=2):
        PCs = self.get_PCs(input_data)
        dimensionality = len(PCs[0])
        range_of_PCs = [range_of_PC_in_one_dim for _ in range(dimensionality)]
        hist_matrix, edges = np.histogramdd(PCs, bins=num_of_bins * np.ones(dimensionality), range=range_of_PCs)
        return np.sum(hist_matrix >= min_num_per_bin), hist_matrix

    def cluster_configs_based_on_distances_in_PC_space(self, folder_for_pdb,
                                                num_clusters, output_folder, radius=0.02):
        """
        This function clusters configurations based on distance in PC space, and generates output pdb files
        containing configurations in each cluster which have distance smaller than 'radius' to the
        corresponding cluster center.
        Why don't I use click-and-save approach (as is done in plotting object in ANN_simulation.py)?
        Because 1. it is not convenient to click for higher-D space, 2. I am lazy to click even for 2D.
        :param temp_autoencoder: autoencoder used to get PCs
        :param folder_for_pdb: folder containing pdb files for input
        :param num_clusters: number of clusters (for K-means)
        :param radius: configs with distance less than 'radius' to the cluster center in PC space will be included in the output pdb
        :return: cluster_pdb_files, cluster_centers
        """
        if not os.path.exists(output_folder):
            subprocess.check_output(['mkdir', output_folder])

        _1 = coordinates_data_files_list([folder_for_pdb])
        _1 = _1.create_sub_coor_data_files_list_using_filter_conditional(lambda x: not 'aligned' in x)
        scaling_factor = CONFIG_49
        input_data = _1.get_coor_data(scaling_factor)
        input_data = Sutils.remove_translation(input_data)
        PCs = self.get_PCs(input_data)
        kmeans = KMeans(init='k-means++', n_clusters=num_clusters, n_init=10)
        kmeans.fit(PCs)
        indices_list = np.array([np.where(kmeans.labels_ == ii)[0]
                                 for ii in range(kmeans.n_clusters)])
        out_pdb_list = []
        for index, item in enumerate(indices_list):
            # save configurations with distance less than 'radius' to corresponding cluster center
            item = list([x for x in item if np.linalg.norm(PCs[x] - kmeans.cluster_centers_[index]) < radius])
            if len(item) > 0:
                output_pdb_name = '%s/%04d_temp_frames_%s.pdb' % \
                                    (output_folder, index, str(list(kmeans.cluster_centers_[index])).replace(' ',''))
                out_pdb_list.append(output_pdb_name)
                _1.write_pdb_frames_into_file_with_list_of_coor_index(item, output_pdb_name, verbose=False)
                # assertion part
                molecule_type.generate_coordinates_from_pdb_files(path_for_pdb=output_pdb_name)
                temp_input_data = np.loadtxt(output_pdb_name.replace('.pdb', '_coordinates.txt')) / scaling_factor
                temp_input_data = Sutils.remove_translation(temp_input_data)
                PCs_of_points_selected = self.get_PCs(input_data=temp_input_data)
                assert_almost_equal(PCs_of_points_selected, PCs[item], decimal=4)
        return out_pdb_list, kmeans.cluster_centers_

    @abc.abstractmethod
    def get_PCs(self, input_data=None):
        """must be implemented by subclasses"""
        pass

    @abc.abstractmethod
    def train(self):
        """must be implemented by subclasses"""
        pass

    @abc.abstractmethod
    def get_output_data(self, input_data=None):
        """must be implemented by subclasses"""
        pass

    @abc.abstractmethod
    def get_mid_result(self, input_data=None):
        """must be implemented by subclasses"""
        pass

    def get_training_error(self):
        input_data = np.array(self._data_set)
        actual_output_data = self.get_output_data()
        if hasattr(self, '_output_data_set') and not self._output_data_set is None:
            expected_output_data = self._output_data_set
        else:
            expected_output_data = input_data
        return np.linalg.norm(expected_output_data - actual_output_data) / sqrt(self._node_num[0] * len(input_data))

    def get_relative_error_for_each_point(self, input_data=None, output_data=None):
        if input_data is None: input_data = self._data_set
        if output_data is None:
            if self._output_data_set is None: output_data = self._data_set
            else: output_data = self._output_data_set
        temp_output = self.get_output_data(input_data)
        relative_err = np.linalg.norm(temp_output - output_data, axis=1) / np.linalg.norm(output_data, axis=1)
        assert (len(relative_err) == len(input_data)), (len(relative_err), len(input_data))
        return relative_err

    def get_fraction_of_variance_explained(self, hierarchical_FVE=False,
                                           output_index_range=None, featurewise=False):
        """ here num_of_PCs is the same with that in get_training_error() """
        index_CV_layer = (len(self._node_num) - 1) / 2
        input_data = np.array(self._data_set)
        actual_output_data = self.get_output_data()
        if hasattr(self, '_output_data_set') and not self._output_data_set is None:
            expected_output_data = self._output_data_set
        else:
            expected_output_data = input_data     # TODO: consider hierarchical case

        if self._hierarchical:
            num_PCs = self._node_num[index_CV_layer] / 2 if self._hidden_layers_type[index_CV_layer - 1] == "Circular" \
                else self._node_num[index_CV_layer]
            length_for_hierarchical_component = expected_output_data.shape[1] / num_PCs
            actual_output_list = [actual_output_data[:,
                                    item * length_for_hierarchical_component:
                                    (item + 1) * length_for_hierarchical_component]
                                               for item in range(num_PCs)]
            expected_output_part = expected_output_data[:, -length_for_hierarchical_component:]
        else:
            actual_output_list = [actual_output_data]    # use list, consistent with hierarchical case
            expected_output_part = expected_output_data
        if not output_index_range is None:
            actual_output_list = [item[:, output_index_range] for item in actual_output_list]
            expected_output_part = expected_output_part[:, output_index_range]
        assert (expected_output_part.shape == actual_output_list[0].shape)
        var_of_expected_output_part = np.var(expected_output_part, axis=0)
        var_of_err_list = [np.var(item - expected_output_part, axis=0)
                                     for item in actual_output_list]
        if featurewise:
            result = [1 - item / var_of_expected_output_part for item in var_of_err_list]
        else:
            result = [1 - np.sum(item) / np.sum(var_of_expected_output_part) for item in var_of_err_list]
        if not hierarchical_FVE:
            result = result[-1]  # it is reasonable to return only last FVE (constructed from all CVs)
        return result

    def get_commands_for_further_biased_simulations(self, list_of_potential_center=None,
                                                    num_of_simulation_steps=None,
                                                    autoencoder_info_file=None,
                                                    force_constant_for_biased=None,
                                                    bias_method=CONFIG_65
                                                    ):
        """this function creates a list of commands for further biased simulations that should be done later,
        either in local machines or on the cluster
        """
        if num_of_simulation_steps is None:
            num_of_simulation_steps = CONFIG_8
        if autoencoder_info_file is None:
            autoencoder_info_file = self._autoencoder_info_file
        PCs_of_network = self.get_PCs()
        if self._hidden_layers_type[1] == "Circular":
            assert (len(PCs_of_network[0]) == self._node_num[2] / 2)
        else:
            assert (len(PCs_of_network[0]) == self._node_num[2])
        if list_of_potential_center is None:
            list_of_potential_center = molecule_type.get_boundary_points(list_of_points=PCs_of_network)
        if bias_method == "US":
            start_from_nearest_config = CONFIG_74
            if start_from_nearest_config:
                nearest_pdb_frame_index_list = []
                _1 = coordinates_data_files_list(['../target/%s' % CONFIG_30])
                _1 = _1.create_sub_coor_data_files_list_using_filter_conditional(lambda x: not 'aligned' in x)
                temp_input_data = _1.get_coor_data(scaling_factor=CONFIG_49)
                temp_input_data = Sutils.remove_translation(temp_input_data)
                temp_all_PCs = list(self.get_PCs(temp_input_data))
                assert len(temp_all_PCs) == np.sum(_1.get_list_of_line_num_of_coor_data_file())
                for item_2 in list_of_potential_center:
                    temp_distances = np.array([np.linalg.norm(item_3 - item_2) for item_3 in temp_all_PCs])
                    index_of_nearest_config = np.argmin(temp_distances)

                    nearest_pdb, nearest_frame_index = _1.get_pdb_name_and_corresponding_frame_index_with_global_coor_index(index_of_nearest_config)
                    nearest_pdb_frame_index_list.append([nearest_pdb, nearest_frame_index])
                    # assertion part
                    temp_input_data_2 = np.loadtxt(nearest_pdb.replace('.pdb', '_coordinates.txt')) / CONFIG_49
                    temp_input_data_2 = Sutils.remove_translation(temp_input_data_2)
                    temp_PC_2 = self.get_PCs(temp_input_data_2)[nearest_frame_index]
                    print(temp_distances[index_of_nearest_config])
                    expected = temp_distances[index_of_nearest_config]
                    actual = np.linalg.norm(temp_PC_2 - item_2)
                    assert_almost_equal(expected, actual, decimal=3)

            if force_constant_for_biased is None:
                if isinstance(molecule_type, Trp_cage):
                    temp_state_coor_file = '../resources/1l2y_coordinates.txt'
                elif isinstance(molecule_type, Alanine_dipeptide):
                    temp_state_coor_file = '../resources/alanine_dipeptide_coordinates.txt'
                elif isinstance(molecule_type, Src_kinase) or isinstance(molecule_type, BetaHairpin):
                    temp_state_coor_file = None
                else:
                    raise Exception('molecule type error')

                if CONFIG_53 == "fixed":
                    force_constant_for_biased = [CONFIG_9 for _ in list_of_potential_center]
                elif CONFIG_53 == "flexible":
                    input_folded_state = np.loadtxt(temp_state_coor_file) / CONFIG_49
                    PC_folded_state = self.get_PCs(Sutils.remove_translation(input_folded_state))[0]
                    print(("PC_folded_state = %s" % str(PC_folded_state)))
                    force_constant_for_biased = [2 * CONFIG_54 / np.linalg.norm(np.array(item) - PC_folded_state) ** 2
                                                 for item in list_of_potential_center]
                elif CONFIG_53 == "truncated":
                    input_folded_state = np.loadtxt(temp_state_coor_file) / CONFIG_49
                    PC_folded_state = self.get_PCs(Sutils.remove_translation(input_folded_state))[0]
                    print(("PC_folded_state = %s" % str(PC_folded_state)))
                    force_constant_for_biased = [min(2 * CONFIG_54 / np.linalg.norm(np.array(item) - PC_folded_state) ** 2,
                                                     CONFIG_9) for item in list_of_potential_center]
                else:
                    raise Exception("error")

            todo_list_of_commands_for_simulations = []
            if CONFIG_48 == 'Cartesian':
                input_data_type = 1
            elif CONFIG_48 == 'cossin':
                input_data_type = 0
            elif CONFIG_48 == 'pairwise_distance':
                input_data_type = 2
            else:
                raise Exception("error input data type")

            for index, potential_center in enumerate(list_of_potential_center):
                if isinstance(molecule_type, Alanine_dipeptide):
                    parameter_list = (str(CONFIG_16), str(num_of_simulation_steps), str(force_constant_for_biased[index]),
                                      '../target/Alanine_dipeptide/network_%d' % self._index,
                                      autoencoder_info_file,
                                      'pc_' + str(potential_center).replace(' ', '')[1:-1],
                                      input_data_type
                                      # need to remove white space, otherwise parsing error
                                      )
                    command = "python ../src/biased_simulation.py %s %s %s %s %s %s --data_type_in_input_layer %d" % parameter_list
                    if CONFIG_42:  # whether the force constant adjustable mode is enabled
                        command = command + ' --fc_adjustable --autoencoder_file %s --remove_previous ' % (
                            '../resources/Alanine_dipeptide/network_%d.pkl' % self._index)
                    if CONFIG_17[1] == "Circular":
                        command += ' --layer_types Tanh,Circular'
                else:
                    parameter_list = (
                            str(CONFIG_16), str(num_of_simulation_steps), str(force_constant_for_biased[index]),
                            '../target/placeholder_1/network_%d/' % self._index, autoencoder_info_file,
                            'pc_' + str(potential_center).replace(' ', '')[1:-1],
                            CONFIG_40, CONFIG_51, index % 2)
                    command = "python ../src/biased_simulation_general.py placeholder_2 %s %s %s %s %s %s %s %s --device %d" % parameter_list
                    command += ' --data_type_in_input_layer %d ' % input_data_type
                    if CONFIG_72: command += ' --fast_equilibration 1'
                    if CONFIG_42:
                        command += ' --fc_adjustable --autoencoder_file %s --remove_previous' % (
                            '../resources/placeholder_1/network_%d.pkl' % self._index)
                    if start_from_nearest_config:
                        command += ' --starting_pdb_file %s --starting_frame %d ' % (nearest_pdb_frame_index_list[index][0],
                                                                                     nearest_pdb_frame_index_list[index][1])
                    if isinstance(molecule_type, Trp_cage): command = command.replace('placeholder_1', 'Trp_cage').replace('placeholder_2', 'Trp_cage')
                    elif isinstance(molecule_type, Src_kinase): command = command.replace('placeholder_1', 'Src_kinase').replace('placeholder_2', '2src')
                    elif isinstance(molecule_type, BetaHairpin): command = command.replace('placeholder_1', 'BetaHairpin').replace('placeholder_2', 'BetaHairpin')
                    else: raise Exception("molecule type not defined")

                todo_list_of_commands_for_simulations += [command]
        elif bias_method == "MTD":
            todo_list_of_commands_for_simulations = []
            self.write_expression_script_for_plumed()
            dimensionality = CONFIG_36
            pc_string = 'pc_' + ','.join(['0' for _ in range(dimensionality)])
            if isinstance(molecule_type, Alanine_dipeptide):
                for mtd_sim_index in range(5):
                    parameter_list = (str(CONFIG_16), str(num_of_simulation_steps), str(mtd_sim_index),
                                      '../target/Alanine_dipeptide/network_%d/' % self._index,
                                      self._autoencoder_info_file, pc_string)
                    command = "python ../src/biased_simulation.py %s %s %s %s %s %s --data_type_in_input_layer 1 --bias_method MTD" % parameter_list
                    todo_list_of_commands_for_simulations += [command]
            elif isinstance(molecule_type, Trp_cage):
                for mtd_sim_index in range(6):
                    parameter_list = (str(CONFIG_16), str(num_of_simulation_steps), str(mtd_sim_index),
                                      '../target/Trp_cage/network_%d/' % self._index, self._autoencoder_info_file,
                                      pc_string, CONFIG_40, CONFIG_51, mtd_sim_index % 2)
                    command = "python ../src/biased_simulation_general.py Trp_cage %s %s %s %s %s %s %s %s --data_type_in_input_layer 1 --bias_method MTD --device %d" % parameter_list
                    todo_list_of_commands_for_simulations += [command]
            else:
                raise Exception("molecule type not defined")
        elif bias_method == "US on pairwise distances":
            todo_list_of_commands_for_simulations = []
            if isinstance(molecule_type, Trp_cage):
                dim_of_CVs = len(list_of_potential_center[0])
                pc_arg_string = ['ann_force.%d' % index_ann for index_ann in range(dim_of_CVs)]
                pc_arg_string = ','.join(pc_arg_string)
                plumed_string = Sutils._get_plumed_script_with_pairwise_dis_as_input(
                    get_index_list_with_selection_statement('../resources/1l2y.pdb', CONFIG_73), CONFIG_49)
                plumed_string += self.get_expression_script_for_plumed(mode='ANN')
                for item_index, item_pc in enumerate(list_of_potential_center):
                    pc_string = ','.join([str(_1) for _1 in item_pc])
                    kappa_string = ','.join([str(CONFIG_9) for _ in range(dim_of_CVs)])
                    temp_plumed_file = '../resources/Trp_cage/temp_plumed_%02d_%02d.txt' % (self._index, item_index)
                    with open(temp_plumed_file, 'w') as my_f:
                        my_f.write(
                            plumed_string + '\nRESTRAINT ARG=%s AT=%s KAPPA=%s LABEL=mypotential\n' % (
                                pc_arg_string, pc_string, kappa_string)
                        )
                    parameter_list = (
                        str(CONFIG_16), str(num_of_simulation_steps), str(CONFIG_9),
                        '../target/Trp_cage/network_%d/' % self._index, 'none',
                        'pc_' + str(item_pc).replace(' ', '')[1:-1],
                        CONFIG_40, CONFIG_51, temp_plumed_file, item_index % 2)
                    command = "python ../src/biased_simulation_general.py Trp_cage %s %s %s %s %s %s %s %s --bias_method plumed_other --plumed_file %s --device %d" % parameter_list
                    todo_list_of_commands_for_simulations += [command]

            else: raise Exception("molecule type not defined")
        else:
            raise Exception("bias method not found")

        return todo_list_of_commands_for_simulations

    def get_proper_potential_centers_for_WHAM(self, list_of_points, threshold_radius, min_num_of_neighbors):
        """
        This function selects some 'proper' potential centers within the domain from list_of_points, by "proper"
        we mean there are at least min_num_of_neighbors data points that are located within the radius of threshold_radius
        of the specific potential center.
        Typically list_of_points could be evenly distributed grid points in PC space
        """
        data_points = np.array(self.get_PCs())
        list_of_points = np.array(list_of_points)
        assert (data_points.shape[1] == list_of_points.shape[1])
        proper_potential_centers = []

        for item in list_of_points:
            neighbors_num = sum([np.dot(item - x, item - x) < threshold_radius * threshold_radius for x in data_points])

            if neighbors_num >= min_num_of_neighbors:
                proper_potential_centers += [item]

        return proper_potential_centers

    def get_proper_potential_centers_for_WHAM_2(self, total_number_of_potential_centers):
        data_points = np.array(self.get_PCs())
        kmeans = KMeans(init='k-means++', n_clusters=total_number_of_potential_centers, n_init=10)
        kmeans.fit(data_points)
        return kmeans.cluster_centers_

    def generate_mat_file_for_WHAM_reweighting(self,
                                               directory_containing_coor_files,
                                               mode="Bayes",  # mode = "standard" or "Bayes"
                                               folder_to_store_files='./standard_WHAM/', dimensionality=2,
                                               input_data_type='cossin',  # input_data_type could be 'cossin' or 'Cartesian'
                                               scaling_factor=CONFIG_49,  # only works for 'Cartesian'
                                               dihedral_angle_range=[1,2],  # only used for alanine dipeptide
                                               starting_index_of_last_few_frames=0,  # number of last few frames used in calculation, 0 means to use all frames
                                               ending_index_of_frames = 0,  # end index, for FES convergence check
                                               random_dataset = False,  # pick random dataset to estimate variance
                                               num_of_bins = 20
                                               ):
        """
        note: 
        dihedral_angle_range, starting_index_of_last_few_frames, ending_index_of_frames, random_dataset 
        may not work for Bayes mode
        num_of_bins only works for Bayes mode
        """
        if folder_to_store_files[-1] != '/':
            folder_to_store_files += '/'
        if not os.path.exists(folder_to_store_files):
            subprocess.check_output(['mkdir', folder_to_store_files])

        if mode == "Bayes":
            for item in ['bias', 'hist', 'traj', 'traj_proj']:
                directory = folder_to_store_files + item
                subprocess.check_output(['mkdir', '-p', directory])
                assert (os.path.exists(directory))
        else: pass

        temp_coor_file_obj = coordinates_data_files_list([directory_containing_coor_files])
        list_of_coor_data_files = temp_coor_file_obj.get_list_of_coor_data_files()
        force_constants = []
        harmonic_centers = []
        window_counts = []
        coords = []
        umbOP = []
        num_of_random_points_to_pick_in_each_file = None
        if random_dataset:
            temp_total_num_points = np.sum(temp_coor_file_obj.get_list_of_line_num_of_coor_data_file())
            temp_total_num_files = len(temp_coor_file_obj.get_list_of_line_num_of_coor_data_file())
            temp_rand_array = np.random.rand(temp_total_num_files)
            temp_rand_array *= (temp_total_num_points / np.sum(temp_rand_array))
            temp_rand_array = temp_rand_array.round()
            temp_rand_array[0] = temp_total_num_points - np.sum(temp_rand_array[1:])
            assert (temp_rand_array.sum() == temp_total_num_points)
            num_of_random_points_to_pick_in_each_file = temp_rand_array.astype(int)
        for temp_index, item in enumerate(list_of_coor_data_files):
            # print('processing %s' %item)
            temp_force_constant = float(item.split('output_fc_')[1].split('_pc_')[0])
            force_constants += [[temp_force_constant] * dimensionality  ]
            temp_harmonic_center_string = item.split('_pc_[')[1].split(']')[0]
            harmonic_centers += [[float(item_1) for item_1 in temp_harmonic_center_string.split(',')]]
            if input_data_type == 'cossin':
                temp_coor = self.get_PCs(molecule_type.get_many_cossin_from_coordinates_in_list_of_files([item]))
            elif input_data_type == 'Cartesian':
                temp_coor = self.get_PCs(Sutils.remove_translation(np.loadtxt(item) / scaling_factor))
            else:
                raise Exception('error input_data_type')

            if random_dataset:
                # data_index_list = random.sample(range(temp_coor.shape[0]), int(0.5 * temp_coor.shape[0]))  # nonrepeated
                # bootstrap for error estimation
                data_index_list = [random.choice(list(range(temp_coor.shape[0])))
                                   for _ in range(num_of_random_points_to_pick_in_each_file[temp_index])]
                # print "random data_index_list"
            else:
                data_index_list = np.arange(temp_coor.shape[0])
                data_index_list = data_index_list[starting_index_of_last_few_frames:]
                if ending_index_of_frames != 0: data_index_list = data_index_list[:ending_index_of_frames]

            temp_coor = temp_coor[data_index_list]
            assert len(temp_coor) == len(data_index_list)
            temp_window_count = temp_coor.shape[0]
            window_counts += [float(temp_window_count)]   # there exists problems if using int

            coords += list(temp_coor)
            if isinstance(molecule_type, Alanine_dipeptide):
                temp_angles = np.array(molecule_type.get_many_dihedrals_from_coordinates_in_file([item]))[data_index_list]
                temp_umbOP = [[a[temp_dihedral_index] for temp_dihedral_index in dihedral_angle_range] for a in temp_angles]
                assert (temp_window_count == len(temp_umbOP)), (temp_window_count, len(temp_umbOP))
                assert (len(dihedral_angle_range) == len(temp_umbOP[0]))
                umbOP += temp_umbOP
            elif isinstance(molecule_type, Trp_cage):
                temp_corresponding_pdb_list = coordinates_data_files_list([item]).get_list_of_corresponding_pdb_files()
                temp_CA_RMSD = np.array(Trp_cage.metric_RMSD_of_atoms(temp_corresponding_pdb_list))
                temp_helix_RMSD = np.array(Trp_cage.metric_RMSD_of_atoms(temp_corresponding_pdb_list,
                                                                atom_selection_statement='resid 2:8 and name CA'))
                umbOP += list(zip(temp_CA_RMSD[data_index_list], temp_helix_RMSD[data_index_list]))

        if mode == "standard":
            max_of_coor = [round(x, 1) + 0.1 for x in list(map(max, list(zip(*coords))))]
            min_of_coor = [round(x, 1) - 0.1 for x in list(map(min, list(zip(*coords))))]
            interval = 0.1

            window_counts = np.array(window_counts)
            sciio.savemat(folder_to_store_files + 'WHAM_nD__preprocessor.mat', {'window_counts': window_counts,
                                                                                'force_constants': force_constants,
                                                                                'harmonic_centers': harmonic_centers,
                                                                                'coords': coords, 'dim': dimensionality,
                                                                                'temperature': 300.0,
                                                                                'periodicity': [[0.0] * dimensionality],
                                                                                'dF_tol': 0.001,
                                                                                'min_gap_max_ORIG': [
                                                                                    [min_of_coor[item_2], interval,
                                                                                     max_of_coor[item_2]] for item_2 in range(dimensionality)]
                                                                                })
            sciio.savemat(folder_to_store_files + 'umbrella_OP.mat',
                          {'umbOP': umbOP
                           })

        elif mode == "Bayes":
            # write info into files
            # 1st: bias potential info
            with open(folder_to_store_files + 'bias/harmonic_biases.txt', 'w') as f_out:
                for item in range(len(force_constants)):
                    f_out.write('%d\t' % (item + 1))
                    for write_item in harmonic_centers[item]:
                        f_out.write('%f\t' % write_item)
                    for write_item in force_constants[item]:
                        f_out.write('%f\t' % write_item)
                    f_out.write("\n")

            # 2nd: trajectory, and projection trajectory in phi-psi space (for reweighting), and histogram
            epsilon = 1e-5
            coords = np.array(coords)
            binEdges_list = []
            with open(folder_to_store_files + 'hist/hist_binEdges.txt', 'w') as f_out:
                for item_100 in range(dimensionality):
                    binEdges = np.linspace(np.min(coords[:, item_100]) - epsilon,
                                           np.max(coords[:, item_100]) + epsilon, num_of_bins + 1)
                    binEdges_list.append(binEdges.tolist())
                    for item in binEdges:
                        f_out.write('%f\t' % item)
                    f_out.write('\n')

            num_of_bins_proj = 40
            umbOP = np.array(umbOP)
            with open(folder_to_store_files + 'hist/hist_binEdges_proj.txt', 'w') as f_out:
                for item_100 in range(len(umbOP[0])):
                    binEdges_proj = np.linspace(np.min(umbOP[:, item_100]) - epsilon,
                                                np.max(umbOP[:, item_100]) + epsilon, num_of_bins_proj + 1)
                    for item in binEdges_proj:
                        f_out.write('%f\t' % item)
                    f_out.write('\n')

            end_index = 0
            for item, count in enumerate(window_counts):
                start_index = int(end_index)
                end_index = int(start_index + count)
                with open(folder_to_store_files + 'traj/traj_%d.txt' % (item + 1), 'w') as f_out_1, \
                        open(folder_to_store_files + 'traj_proj/traj_%d.txt' % (item + 1), 'w') as f_out_2, \
                        open(folder_to_store_files + 'hist/hist_%d.txt' % (item + 1), 'w') as f_out_3:
                    for line in coords[start_index:end_index]:
                        for item_1 in line:
                            f_out_1.write('%f\t' % item_1)

                        f_out_1.write("\n")

                    for line in umbOP[start_index:end_index]:
                        for item_1 in line:
                            f_out_2.write('%f\t' % item_1)

                        f_out_2.write("\n")

                    temp_hist, _ = np.histogramdd(np.array(coords[start_index:end_index]),
                                                     bins=binEdges_list)
                    for _1 in temp_hist.flatten():
                        f_out_3.write('%d\t' % _1)
        else:
            raise Exception("error mode!")

        return

    @staticmethod
    def tune_hyperparams_using_Bayes_optimization(in_data, out_data, folder, lr_range, momentum_range,
                                                  lr_log_scale=True, train_num_per_iter=5,
                                                  total_iter_num=20,
                                                  num_training_per_param=3,
                                                  print_command_only=False   # only print commands, does no training, basically doing random search of parameters
                                                  ):
        """use Bayes optimization for tuning hyperparameters,
        see http://neupy.com/2016/12/17/hyperparameter_optimization_for_neural_networks.html#bayesian-optimization"""
        def next_parameter_by_ei(best_y, y_mean, y_std, x_choices, num_choices):
            expected_improvement = (y_mean + 1.0 * y_std) - best_y
            max_index = np.argsort(expected_improvement)[-num_choices:]
            return x_choices[max_index], expected_improvement[max_index]

        from sklearn.gaussian_process import GaussianProcessRegressor
        import glob
        for iter_index in range(total_iter_num):
            autoencoder_files = sorted(glob.glob('%s/*.pkl' % folder))
            if len(autoencoder_files) == 0:  # use random search as the start
                params = np.random.uniform(size=(train_num_per_iter, 2))
                params[:, 1] = params[:, 1] * (momentum_range[1] - momentum_range[0]) + momentum_range[0]
                if lr_log_scale:
                    params[:, 0] = np.exp(
                        params[:, 0] * (np.log(lr_range[1]) - np.log(lr_range[0])) + np.log(lr_range[0]))
                else:
                    params[:, 0] = params[:, 0] * (lr_range[1] - lr_range[0]) + lr_range[0]
                next_params = params[:]
            else:  # generate params based on Bayes optimization
                gp = GaussianProcessRegressor()
                X_train, y_train = [], []
                for item_AE_file in autoencoder_files:
                    temp_AE = autoencoder.load_from_pkl_file(item_AE_file)
                    assert (isinstance(temp_AE, autoencoder_Keras))
                    X_train.append(temp_AE._network_parameters[:2])
                    if not np.isnan(temp_AE.get_fraction_of_variance_explained()):
                        y_train.append(temp_AE.get_fraction_of_variance_explained())
                    else:
                        y_train.append(-1.0)  # TODO: is it good?
                X_train, y_train = np.array(X_train), np.array(y_train)
                print(np.concatenate([X_train,y_train.reshape(y_train.shape[0], 1)], axis=-1))
                current_best_y_train = np.max(y_train)
                gp.fit(X_train, y_train)
                params = np.random.uniform(size=(100, 2))
                params[:, 1] = params[:, 1] * (momentum_range[1] - momentum_range[0]) + momentum_range[0]
                if lr_log_scale:
                    params[:, 0] = np.exp(
                        params[:, 0] * (np.log(lr_range[1]) - np.log(lr_range[0])) + np.log(lr_range[0]))
                else:
                    params[:, 0] = params[:, 0] * (lr_range[1] - lr_range[0]) + lr_range[0]
                y_mean, y_std = gp.predict(params, return_std=True)
                next_params, next_ei = next_parameter_by_ei(current_best_y_train, y_mean, y_std, params, train_num_per_iter)
                print(next_params, next_ei)

            assert (len(next_params) == train_num_per_iter)
            command_list = []
            cuda_index = 0
            for item_param in next_params:
                for index in range(num_training_per_param):
                    command = "python train_network_and_save_for_iter.py 1447 --num_of_trainings 1 --lr_m %f,%f --output_file %s/temp_%02d_%s_%02d.pkl --in_data %s --out_data %s" % (
                        item_param[0], item_param[1], folder, iter_index,
                        str(item_param).strip().replace(' ','').replace('[','').replace(']',''), index, in_data, out_data
                    )
                    if temp_home_directory == "/home/kengyangyao":
                        command = "THEANO_FLAGS=device=cuda%d " % cuda_index + command
                        cuda_index = 1 - cuda_index      # use two GPUs
                    command_list.append(command)
            if not print_command_only:
                num_failed_jobs = Helper_func.run_multiple_jobs_on_local_machine(
                    command_list, num_of_jobs_in_parallel=2)
            else:
                for item_commad in command_list: print item_commad
                return
            print("num_failed_jobs = %d" % num_failed_jobs)
        return


class autoencoder_Keras(autoencoder):
    def _init_extra(self,
                    network_parameters = CONFIG_4,
                    batch_size = 100,
                    enable_early_stopping=True,
                    mse_weights=None
                    ):
        self._network_parameters = network_parameters
        if not isinstance(self._network_parameters[4], list):
            self._network_parameters[4] = [self._network_parameters[4]] * (len(self._node_num) - 1)    # simplify regularization for deeper networks
        assert isinstance(self._network_parameters[4], list)
        self._batch_size = batch_size
        self._enable_early_stopping = enable_early_stopping
        self._mse_weights = mse_weights
        self._molecule_net_layers = None              # why don't I save molecule_net (Keras model) instead? since it it not picklable:
                                                      # https://github.com/luispedro/jug/issues/30
                                                      # https://keras.io/getting-started/faq/#how-can-i-save-a-keras-model
                                                      # obsolete: should not save _molecule_net_layers in the future, kept for backward compatibility
        return

    def get_output_data(self, input_data=None):
        if input_data is None: input_data = self._data_set
        return self._molecule_net.predict(input_data)

    def get_PCs(self, input_data=None):
        index_CV_layer = (len(self._node_num) - 1) / 2
        if input_data is None: input_data = self._data_set
        if self._hidden_layers_type[index_CV_layer - 1] == "Circular":
            PCs = np.array([[acos(item[2 * _1]) * np.sign(item[2 * _1 + 1]) for _1 in range(len(item) / 2)]
                   for item in self._encoder_net.predict(input_data)])
            assert (len(PCs[0]) == self._node_num[index_CV_layer] / 2), (len(PCs[0]), self._node_num[index_CV_layer] / 2)
        else:
            PCs = self._encoder_net.predict(input_data)
            assert (len(PCs[0]) == self._node_num[index_CV_layer])
        return PCs

    def get_outputs_from_PC(self, input_PC):
        index_CV_layer = (len(self._node_num) - 1) / 2
        if self._hidden_layers_type[index_CV_layer - 1] == "Circular": raise Exception('not implemented')
        inputs = Input(shape=(self._node_num[index_CV_layer],))
        x = inputs
        for item in self._molecule_net.layers[-index_CV_layer:]:
            x = item(x)     # using functional API
        model = Model(input=inputs, output=x)
        return model.predict(input_PC)

    def layerwise_pretrain(self, data, dim_in, dim_out):
        """ref: https://www.kaggle.com/baogorek/autoencoder-with-greedy-layer-wise-pretraining/notebook"""
        data_in = Input(shape=(dim_in,))
        encoded = Dense(dim_out, activation='tanh')(data_in)
        data_out = Dense(dim_in, activation='tanh')(encoded)
        temp_ae = Model(inputs=data_in, outputs=data_out)
        encoder = Model(inputs=data_in, outputs=encoded)
        sgd = SGD(lr=0.3, decay=0, momentum=0.9, nesterov=True)
        temp_ae.compile(loss='mean_squared_error', optimizer=sgd)
        encoder.compile(loss='mean_squared_error', optimizer=sgd)
        temp_ae.fit(data, data, epochs=20, batch_size=50,
                    validation_split=0.20, shuffle=True, verbose=False)
        encoded_data = encoder.predict(data)
        reconstructed = temp_ae.predict(data)
        var_of_output = np.sum(np.var(data, axis=0))
        var_of_err = np.sum(np.var(reconstructed - data, axis=0))
        fve = 1 - var_of_err / var_of_output
        return temp_ae.layers[1].get_weights(), encoded_data, fve

    def get_pca_fve(self, data=None):
        """compare the autoencoder against PCA"""
        if data is None: data = self._data_set
        pca = PCA(n_components=self._node_num[(len(self._node_num) - 1) / 2])
        actual_output = pca.inverse_transform(pca.fit_transform(data))
        return (1 - np.sum((actual_output - data).var(axis=0)) / np.sum(data.var(axis=0)), pca)

    def train(self, hierarchical=None, hierarchical_variant = None):
        act_funcs = [item.lower() for item in self._hidden_layers_type] + [self._out_layer_type.lower()]
        if hierarchical is None: hierarchical = self._hierarchical
        if hierarchical_variant is None: hierarchical_variant = self._hi_variant
        node_num = self._node_num
        data = self._data_set
        if hasattr(self, '_output_data_set') and not self._output_data_set is None:
            print ("outputs may be different from inputs")
            output_data_set = self._output_data_set
        else:
            output_data_set = data

        index_CV_layer = (len(node_num) - 1) / 2
        num_CVs = node_num[index_CV_layer] / 2 if act_funcs[index_CV_layer - 1] == "circular" else \
            node_num[index_CV_layer]
        if hierarchical:
            # functional API: https://keras.io/getting-started/functional-api-guide
            temp_output_shape = output_data_set.shape
            output_data_set = np.repeat(output_data_set, num_CVs, axis=0).reshape(temp_output_shape[0],
                                        temp_output_shape[1] * num_CVs)   # repeat output for hierarchical case
            # check if the output data are correct
            temp_data_for_checking = output_data_set[0]
            for item in range(num_CVs):
                assert_almost_equal (
                    temp_data_for_checking[item * temp_output_shape[1]: (item + 1) * temp_output_shape[1]],
                    temp_data_for_checking[:temp_output_shape[1]])
            self._output_data_set = output_data_set
            inputs_net = Input(shape=(node_num[0],))
            x = Dense(node_num[1], activation=act_funcs[0],
                      kernel_regularizer=l2(self._network_parameters[4][0]))(inputs_net)
            for item in range(2, index_CV_layer):
                x = Dense(node_num[item], activation=act_funcs[item - 1], kernel_regularizer=l2(self._network_parameters[4][item - 1]))(x)
            if act_funcs[index_CV_layer - 1] == "circular":
                x = Dense(node_num[index_CV_layer], activation='linear',
                            kernel_regularizer=l2(self._network_parameters[4][index_CV_layer - 1]))(x)
                x = Reshape((num_CVs, 2), input_shape=(node_num[index_CV_layer],))(x)
                x = Lambda(temp_lambda_func_for_circular_for_Keras)(x)
                encoded = Reshape((node_num[index_CV_layer],))(x)
                encoded_split = [temp_lambda_slice_layers_circular[item](encoded) for item in range(num_CVs)]
            else:
                encoded_split = [Dense(1, activation=act_funcs[index_CV_layer - 1],
                                kernel_regularizer=l2(self._network_parameters[4][index_CV_layer - 1]))(x) for _ in range(num_CVs)]
                encoded = layers.Concatenate()(encoded_split)

            if hierarchical_variant == 0:  # this is logically equivalent to original version by Scholz
                x_next = [Dense(node_num[index_CV_layer + 1], activation='linear',
                                kernel_regularizer=l2(self._network_parameters[4][index_CV_layer]))(item) for item in encoded_split]
                x_next_1 = [x_next[0]]
                for item in range(2, len(x_next) + 1):
                    x_next_1.append(layers.Add()(x_next[:item]))
                if act_funcs[index_CV_layer] == 'tanh':
                    x_next_1 = [temp_lambda_tanh_layer(item) for item in x_next_1]
                elif act_funcs[index_CV_layer] == 'sigmoid':
                    x_next_1 = [temp_lambda_sigmoid_layer(item) for item in x_next_1]
                elif act_funcs[index_CV_layer] == 'linear':
                    x_next_1 = x_next_1
                else:
                    raise Exception('activation function not implemented')
                assert (len(x_next) == len(x_next_1))
                for item_index in range(index_CV_layer + 2, len(node_num) - 1):
                    x_next_1 = [Dense(node_num[item_index], activation=act_funcs[item_index - 1], kernel_regularizer=l2(self._network_parameters[4][item_index - 1]))(item_2)
                                for item_2 in x_next_1]
                shared_final_layer = Dense(node_num[-1], activation=act_funcs[-1],
                                           kernel_regularizer=l2(self._network_parameters[4][-1]))
                outputs_net = layers.Concatenate()([shared_final_layer(item) for item in x_next_1])
                encoder_net = Model(inputs=inputs_net, outputs=encoded)
                molecule_net = Model(inputs=inputs_net, outputs=outputs_net)
            elif hierarchical_variant == 1:   # simplified version, no shared layer after CV (encoded) layer
                concat_layers = [encoded_split[0]]
                concat_layers += [layers.Concatenate()(encoded_split[:item]) for item in range(2, num_CVs + 1)]
                x = [Dense(node_num[index_CV_layer + 1], activation=act_funcs[index_CV_layer],
                                kernel_regularizer=l2(self._network_parameters[4][index_CV_layer]))(item) for item in concat_layers]
                for item_index in range(index_CV_layer + 2, len(node_num) - 1):
                    x = [Dense(node_num[item_index], activation=act_funcs[item_index - 1],
                               kernel_regularizer=l2(self._network_parameters[4][item_index - 1]))(item) for item in x]
                x = [Dense(node_num[-1], activation=act_funcs[-1],
                                kernel_regularizer=l2(self._network_parameters[4][-1]))(item) for item in x]
                outputs_net = layers.Concatenate()(x)
                encoder_net = Model(inputs=inputs_net, outputs=encoded)
                molecule_net = Model(inputs=inputs_net, outputs=outputs_net)
            elif hierarchical_variant == 2:
                # boosted hierarchical autoencoders, CV i in encoded layer learns remaining error that has
                # not been learned by previous CVs
                x = [Dense(node_num[index_CV_layer + 1], activation=act_funcs[index_CV_layer],
                           kernel_regularizer=l2(self._network_parameters[4][index_CV_layer]))(item) for item in encoded_split]
                for item_index in range(index_CV_layer + 2, len(node_num) - 1):
                    x = [Dense(node_num[item_index], activation=act_funcs[item_index - 1],
                               kernel_regularizer=l2(self._network_parameters[4][item_index - 1]))(item) for item in x]
                x = [Dense(node_num[-1], activation=act_funcs[-1],
                           kernel_regularizer=l2(self._network_parameters[4][-1]))(item) for item in x]
                x_out = [x[0]]
                for item in range(2, len(x) + 1):
                    x_out.append(layers.Add()(x[:item]))
                assert (len(x_out) == len(x))
                outputs_net = layers.Concatenate()(x_out)
                encoder_net = Model(inputs=inputs_net, outputs=encoded)
                molecule_net = Model(inputs=inputs_net, outputs=outputs_net)
            else: raise Exception('error variant')
            # print molecule_net.summary()
            loss_function = get_mse_weighted(self._mse_weights)
        # elif num_of_hidden_layers != 3:
        #     raise Exception('not implemented for this case')
        else:
            inputs_net = Input(shape=(node_num[0],))
            x = Dense(node_num[1], activation=act_funcs[0],
                      kernel_regularizer=l2(self._network_parameters[4][0]))(inputs_net)
            for item in range(2, index_CV_layer):
                x = Dense(node_num[item], activation=act_funcs[item - 1], kernel_regularizer=l2(self._network_parameters[4][item - 1]))(x)
            if act_funcs[index_CV_layer - 1] == "circular":
                x = Dense(node_num[index_CV_layer], activation='linear',
                            kernel_regularizer=l2(self._network_parameters[4][index_CV_layer - 1]))(x)
                x = Reshape((node_num[index_CV_layer] / 2, 2), input_shape=(node_num[index_CV_layer],))(x)
                x = Lambda(temp_lambda_func_for_circular_for_Keras)(x)
                encoded = Reshape((node_num[index_CV_layer],))(x)
            else:
                encoded = Dense(node_num[index_CV_layer], activation=act_funcs[index_CV_layer - 1],
                            kernel_regularizer=l2(self._network_parameters[4][index_CV_layer - 1]))(x)
            x = Dense(node_num[index_CV_layer + 1], activation=act_funcs[index_CV_layer],
                      kernel_regularizer=l2(self._network_parameters[4][index_CV_layer]))(encoded)
            for item_index in range(index_CV_layer + 2, len(node_num)):
                x = Dense(node_num[item_index], activation=act_funcs[item_index - 1],
                          kernel_regularizer=l2(self._network_parameters[4][item_index - 1]))(x)
            molecule_net = Model(inputs=inputs_net, outputs=x)
            encoder_net = Model(inputs=inputs_net, outputs=encoded)
            loss_function = get_mse_weighted(self._mse_weights)

        try:
            from keras.utils import plot_model
            Helper_func.backup_rename_file_if_exists('model.png')
            plot_model(molecule_net, show_shapes=True, to_file='model.png')
        except: pass

        temp_optimizer_name = "Adam"
        if temp_optimizer_name == 'SGD':
            temp_optimizer = SGD(lr=self._network_parameters[0],
                                   momentum=self._network_parameters[1],
                                   decay=self._network_parameters[2],
                                   nesterov=self._network_parameters[3])
        elif temp_optimizer_name == 'Adam':
            temp_optimizer = Adam(lr=self._network_parameters[0])

        molecule_net.compile(loss=loss_function, metrics=[loss_function],
                             optimizer= temp_optimizer)
        encoder_net.compile(loss=loss_function, metrics=[loss_function],
                             optimizer=temp_optimizer)  # not needed, but do not want to see endless warning...
        pretraining = False
        data_for_pretraining = self._data_set
        if pretraining:
            for index_layer in range(1, 3):   # TODO: currently only for first 2 Dense layers
                temp_weights, data_for_pretraining, fve = self.layerwise_pretrain(
                    data_for_pretraining, self._node_num[index_layer - 1], self._node_num[index_layer])
                molecule_net.layers[index_layer].set_weights(temp_weights)
                print "fve of pretraining for layer %d = %f" % (index_layer, fve)

        training_print_info = '''training, index = %d, maxEpochs = %d, node_num = %s, layers = %s, num_data = %d,
parameter = %s, optimizer = %s, hierarchical = %d with variant %d, FVE should not be less than %f (PCA)\n''' % (
            self._index, self._epochs, str(self._node_num),
            str(act_funcs), len(data), str(self._network_parameters), temp_optimizer_name,
            self._hierarchical, self._hi_variant, self.get_pca_fve()[0])

        print(("Start " + training_print_info + str(datetime.datetime.now())))
        call_back_list = []
        earlyStopping = EarlyStopping(monitor='val_loss', patience=100, verbose=0, mode='min')
        if self._enable_early_stopping:
            call_back_list += [earlyStopping]
        [train_in, train_out] = Helper_func.shuffle_multiple_arrays([data, output_data_set])
        train_history = molecule_net.fit(train_in, train_out, epochs=self._epochs, batch_size=self._batch_size,
                                         verbose=False, validation_split=0.2, callbacks=call_back_list)

        dense_layers = [item for item in molecule_net.layers if isinstance(item, Dense)]
        for _1 in range(2):  # check first two layers only
            assert (dense_layers[_1].get_weights()[0].shape[0] == node_num[_1]), (
            dense_layers[_1].get_weights()[0].shape[1], node_num[_1])  # check shapes of weights

        self._connection_between_layers_coeffs = [item.get_weights()[0].T.flatten() for item in
                                                  molecule_net.layers if isinstance(item,
                                                                                    Dense)]  # transpose the weights for consistency
        self._connection_with_bias_layers_coeffs = [item.get_weights()[1] for item in molecule_net.layers if
                                                    isinstance(item, Dense)]

        print(('Done ' + training_print_info + str(datetime.datetime.now())))
        self._molecule_net = molecule_net
        self._encoder_net = encoder_net
        try:
            fig, axes = plt.subplots(1, 2)
            axes[0].plot(train_history.history['loss'])
            axes[1].plot(train_history.history['val_loss'])
            fig.suptitle(str(self._node_num) + str(self._network_parameters) + temp_optimizer_name)
            png_file = 'history_%02d.png' % self._index
            Helper_func.backup_rename_file_if_exists(png_file)
            fig.savefig(png_file)
        except: print("training history not plotted!"); pass
        return self, train_history


def temp_lambda_func_for_circular_for_Keras(x):
    """This has to be defined at the module level here, otherwise the pickle will not work
    """
    return x / ((x ** 2).sum(axis=2, keepdims=True).sqrt())

temp_lambda_tanh_layer = Lambda(lambda x: K.tanh(x))
temp_lambda_sigmoid_layer = Lambda(lambda x: K.sigmoid(x))
# not sure if there are better ways to do this, since Lambda layer has to be defined at top level of the file,
# following line does not work
# temp_lambda_slice_layers = [Lambda(lambda x: x[:, [index]], output_shape=(1,)) for index in range(20)]
temp_lambda_slice_layers_circular = [
    Lambda(lambda x: x[:, [0,1]], output_shape=(2,)),   Lambda(lambda x: x[:, [2,3]], output_shape=(2,)),
    Lambda(lambda x: x[:, [4,5]], output_shape=(2,)),   Lambda(lambda x: x[:, [6,7]], output_shape=(2,)),
    Lambda(lambda x: x[:, [8,9]], output_shape=(2,)),   Lambda(lambda x: x[:, [10,11]], output_shape=(2,)),
    Lambda(lambda x: x[:, [12,13]], output_shape=(2,)), Lambda(lambda x: x[:, [14,15]], output_shape=(2,)),
    Lambda(lambda x: x[:, [16,17]], output_shape=(2,)), Lambda(lambda x: x[:, [18,19]], output_shape=(2,))
]

def get_hierarchical_weights(weight_factor_for_hierarchical_err = 1):
    # following is custom loss function for hierarchical error of hierarchical autoencoder
    # it may be useful to assign different weights for hierarchical error,
    # instead of having E = E_1 + E_{1,2} + E_{1,2,3}
    # we have E = a^2 E_1 + a E_{1,2} + E_{1,2,3}, a < 1
    # to avoid too large bias towards reconstruction error using first few components
    # see progress report 20171101
    weight_for_hierarchical_error = np.ones(CONFIG_3[-1] * CONFIG_36)
    for item in range(CONFIG_36):
        weight_for_hierarchical_error[: item * CONFIG_3[-1]] *= weight_factor_for_hierarchical_err
    return weight_for_hierarchical_error

# weighted MSE
weight_for_MSE = get_hierarchical_weights()
# if CONFIG_44:
#     print "MSE is weighted by %s" % str(weight_for_MSE)

def get_mse_weighted(weight_for_MSE=None):   # take weight as input, return loss function
    if weight_for_MSE is None:
        weight_for_MSE = 1
    else:
        print("error weighted by %s" % str(weight_for_MSE))
    def mse_weighted(y_true, y_pred):
        return K.mean(K.variable(weight_for_MSE) * K.square(y_pred - y_true), axis=-1)  # TODO: do this later
        #  return K.mean(K.square(y_pred - y_true), axis=-1)
    return mse_weighted

mse_weighted = get_mse_weighted()      # requires a global mse_weighted(), for backward compatibility

