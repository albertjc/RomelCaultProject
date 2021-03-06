import warnings

class HyperparameterSearcher:
    """
    Module for automating hyperparameter search.
    Search plans are returned as lists of dictionaries.
    A hyperparameter generator can be
    - list: values are generated by selecting a random element (default is the first element)
    - function with one input: values are generated by calling the function (no default)
    - other type: the generator is returned as the value (default is the generator)

    Example use:

    hyp = {
        'mixing_rate': np.random.uniform(0, 1)
        'batch_size': 32,
        'learning_rate': [0.01, 0.001]
    }
    hyp_defaults={'mixing_rate': 0.5}
    searcher = HyperparameterSearcher(hyp, hyp_defaults)
    for hyp_dict in searcher.random_search(100):
        for repetition in range(3):
            run_experiment(hyp_dict)

    """
    def __init__(self, hyperparams, hyp_defaults=None):
        """
        :param hyperparams: dict mapping hyperparameter names to hyperparameter generators
        :param hyp_defaults: dict mapping hyperparameter names to values which override the
                             defaults of the hyperparameters in the hyperparams argument
        """
        if hyp_defaults is None:
            hyp_defaults = {}
        self.hyperparams = hyperparams.copy()
        self.hyp_defaults = hyp_defaults
        self._check_config()

    def _check_config(self):
        errors = []

        all_hyp = set(self.hyperparams.keys())
        callable_hyp = set([hyp_name for hyp_name, hyp_gen in self.hyperparams.items()
                            if callable(hyp_gen)])
        non_callable_hyp = all_hyp - callable_hyp
        
        # check that hyp_defaults references proper hyperparameters
        default_errors = set(self.hyp_defaults.keys()) - all_hyp
        if len(default_errors) != 0:
            errors.append(f'{default_errors} are not hyperparameters')

        # check that callable hyperparameters take no arguments
        for hyp_name in callable_hyp:
            try:
                self.hyperparams[hyp_name]()
            except Exception as ex:
                errors.append(f'{hyp_name} call error: {ex}')
            
        # check that all hyperparameters are defaults
        covered_defaults = (non_callable_hyp | set(self.hyp_defaults.keys()))
        not_covered_defaults = set(self.hyperparams.keys()) - covered_defaults
        if len(not_covered_defaults) != 0:
            warnings.warn(f'{not_covered_defaults} have no default values')

        assert len(errors) == 0, errors

    def _choose_random(self, hyp_name):
        generator = self.hyperparams[hyp_name]
        return self._generate_random(generator)

    @staticmethod
    def _generate_random(generator):
        if isinstance(generator, list):
            return np.random.choice(generator)
        elif callable(generator):
            return generator()
        else:
            return generator

    def _choose_default(self, hyp_name):
        if hyp_name in self.hyp_defaults.keys():
            return self.hyp_defaults[hyp_name]
        generator = self.hyperparams[hyp_name]
        if isinstance(generator, list):
            return generator[0]
        elif callable(generator):
            warnings.warn('Missing default for hyperparameter {}'.format(hyp_name))
            return generator()
        else:
            return generator

    def default_dict(self):
        # default hyperparameter dict
        return dict((hyp_name, self._choose_default(hyp_name))
                    for hyp_name in self.hyperparams.keys())

    def random_dict(self):
        # random hyperparameter dict
        return dict((hyp_name, self._choose_random(hyp_name))
                    for hyp_name, hyp_gen in self.hyperparams.items())

    def default_search(self, n=1):
        # list of n default hyperparameter dictionaries
        return [self.default_dict() for i in range(n)]

    def random_search(self, n=1):
        # list of n random search hyperparameter dictionaries
        return [self.random_dict() for i in range(n)]

    def one_value_search(self, interests, n=1):
        """
        With k hyperparameters, return the concatenation of (n / k) chunks, where chunk i is a
        hyperparameter search where
        - hyperparameter i is chosen randomly
        - other hyperparameters are chosen using their default values
        :param interests: list of hyperparameter names
        :param n: number of hyperparameter dictionaries in total
        :return: list of n hyperparameter dictionaries
        """
        assert isinstance(interests, list)
        n_rep = n // len(interests)
        assert n_rep > 0, f'Error: n_rep=={n_rep} when n={n} and len(interest)={len(interests)}'
        result_search = self.default_search(n=n)
        for i in range(n):
            hyp_name = interests[i // n_rep]
            result_search[i][hyp_name] = self._choose_random(hyp_name)
        return result_search
    
    def one_value_grid_search(self, interests):
        """
        Return a subset of grid search of the variables in interest where only 1 variable is
        different from the default at a time
        :param interests: list of hyperparameter names
        :return: list of n hyperparameter dictionaries
        """
        assert isinstance(interests, list)
        assert all([isinstance(self.hyperparams[interest], list) for interest in interests])

        n_unique_tuples = (sum([len(self.hyperparams[interest]) for interest in interests]) +
                           1 - len(interests))

        # construct hyperparameter dicts without default values
        non_default_hyperparams = {}
        for hyp_name in interests:
            non_default_list = list(self.hyperparams[hyp_name])
            non_default_list.pop(non_default_list.index(self._choose_default(hyp_name)))
            non_default_hyperparams[hyp_name] = non_default_list

        result_search = self.default_search(n=n_unique_tuples)
        search_i = 1  # first dictionary is the default
        for hyp_name in interests:
            for value in non_default_hyperparams[hyp_name]:
                result_search[search_i][hyp_name] = value
                search_i += 1
        assert search_i == n_unique_tuples
        return result_search

    def custom_search(self, overwritten_hyp, n=1):
        """
        default search but with overwritten generators
        :param overwritten_hyp: dict mapping hyperparameter names to hyperparameter generators,
                                which overrides the corresponding hyperparameter generators for
                                this search only
        :param n: number of hyperparameter dictionaries in total
        :return:list of n hyperparameter dictionaries
        """
        result_search = self.default_search(n=n)
        for i in range(n):
            for hyp_name, hyp_gen in overwritten_hyp.items():
                result_search[i][hyp_name] = self._generate_random(hyp_gen)
        return result_search