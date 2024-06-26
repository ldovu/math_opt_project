import numpy as np
from BeamSearch import beam_search


# NOTE: The matrices containing the data have an extra columns of "-1" in
#       position 0 in order to have job=job_index
class PreProcess:

    def __init__(self, file_path):
        self.GS_time_steps = None
        self.GS_processed_jobs = None
        self.T = None
        self.time_steps = None
        self.processed_jobs = None
        self.setup_bar_times = None
        self.n_jobs = None
        self.release_dates = None
        self.processing_times = None
        self.setup_times = None

        self.R = None
        self.O = None
        self.R_as_matrix = None  # Just for internal use

        self.arcs = None
        self.range_arcs = None
        self.range_A1 = None
        self.range_A2 = None
        self.range_A3 = None
        self.range_A4 = None

        self.read_dat(file_path)
        # We employ deterministic (gamma=0) beam search to find an upped bound for the timespan
        self.T, _ = beam_search(omega=2, N=3, gamma=0, n_jobs=self.n_jobs, release_dates=self.release_dates,
                                setup_times=self.setup_times, processing_times=self.processing_times)
        self.set_setup_bar_times()
        self.set_R()
        self.set_O()

        self.set_As_and_arcs()

    # NOTE: This function reads a file .dat with a specific structure (see paper's github in the README.md file
    # NOTE: The matrices containing the data have an extra column, or row, of "-1" whne needed in
    #       position 0 in order to have job=job_index
    def read_dat(self, file_path):

        if file_path.endswith(".dat"):
            with open(file_path, 'r') as file:
                first_line = file.readline().replace("\n", "")
                first_elements = [int(x) for x in first_line.split(" ") if x]
                self.n_jobs = first_elements[0]

                # NOTE: The matrices containing the data have an extra columns of "-1" in
                #       position 0 in order to have job=job_index
                self.release_dates = np.full(self.n_jobs + 1, -1)
                self.processing_times = np.full(self.n_jobs + 1, -1)
                self.setup_times = np.full([self.n_jobs + 1, self.n_jobs + 1], -1, dtype=int)

                setup_matrix_rows = 0

                for i, line in enumerate(file):

                    line = line.replace("\n", "")
                    elements = [int(x) for x in line.split(" ") if x]

                    line_length = len(elements)

                    if 2 <= i < 2 + self.n_jobs:
                        if line_length != 4:
                            raise Exception(f"""Something is wrong with the {file_path} file format: Error {1}""")
                        job = elements[0]

                        self.release_dates[job] = elements[1]
                        self.processing_times[job] = elements[2]
                        continue

                    if i >= 2 + self.n_jobs:

                        if line_length != self.n_jobs:
                            raise Exception(f"""Something is wrong with the {file_path} file format: Error {2}""")

                        setup_matrix_rows = setup_matrix_rows + 1

                        row_index = setup_matrix_rows - 1

                        for column_index, element in enumerate(elements):

                            job = column_index + 1
                            # Ignore setup times between a job and its self
                            if job == row_index:
                                continue

                            else:
                                self.setup_times[row_index, job] = element

                if setup_matrix_rows != self.n_jobs + 1:
                    raise Exception(f"""Something is wrong with the {file_path} file format: Error {3}""")

        else:
            try:
                self.n_jobs = int(file_path.split("/")[-1].split("n")[0])
                if "/" in file_path:
                    folder_file_path = file_path
                else:
                    folder_file_path = "GeneratedInstances/" + file_path
                self.release_dates = np.loadtxt(folder_file_path + "/release_dates.csv", delimiter=",", dtype=int)
                self.processing_times = np.loadtxt(folder_file_path + "/processing_times.csv", delimiter=",", dtype=int)
                self.setup_times = np.loadtxt(folder_file_path + "/setup_times.csv", delimiter=",", dtype=int)
            except Exception as e:
                raise Exception(f"""Something is wrong with the {file_path} file format: Error {4}""")

    # Takes the minimum setup time for each job (excluding -1 values)
    def set_setup_bar_times(self):

        self.setup_bar_times = [-1]

        for job in range(1, self.n_jobs + 1):
            column = [row[job] for row in self.setup_times if row[job] != -1]
            self.setup_bar_times.append(min(column))

    # NOTE: R_as_matrix[i] is a list of times t that represent the nodes (i, t)
    #       While the list R is a flat list of the nodes (i, t)
    def set_R(self):

        self.R = []

        self.R_as_matrix = [[] for _ in range(self.n_jobs + 1)]
        self.R_as_matrix[0].append(-1)

        for job in range(1, self.n_jobs + 1):
            for t in range((self.setup_bar_times[job] + self.release_dates[job] + self.processing_times[job]),
                           self.T + 1):
                self.R_as_matrix[job].append(t)
                self.R.append((job, t))

    # NOTE: O is a list of nodes (0, t)
    def set_O(self):
        self.O = [(0, t) for t in range(self.T + 1)]

    # NOTE: We compute A1, saving the results in the list self.arcs with the structure:
    #            self.arcs[0]="A1"
    #            self.arcs[1]="i"
    #            self.arcs[2]="t"
    #            self.arcs[3]="j"
    #            self.arcs[4]="t + s_ij + p_j"
    #       where (i, t) and (j, t + s_ij + p_j) are nodes of R
    def set_A1(self):
        arcs_counter = 0
        # For each couple of jobs (i, j), excluding the dummy job 0, compute all arcs of type:
        #   (i, t) -> (j, t + s_ij + p_j)
        for job_i in range(1, self.n_jobs + 1):
            for job_j in range(1, self.n_jobs + 1):

                # Skip if i==j
                if job_i == job_j:
                    continue

                else:
                    # time_span = s_ij + p_j
                    time_span = self.setup_times[job_i][job_j] + \
                                self.processing_times[job_j]
                    # Get the smallest t from the set of nodes of type: (job_i, t)
                    first_time_i = self.R_as_matrix[job_i][0]

                    # Get the smallest t from the set of arcs of type: (job_i, t) -> (job_j, t+time_span)
                    release_date_j = self.release_dates[job_j]
                    initial_time = max(first_time_i, release_date_j)
                    # Get the largest t from the set of arcs of type: (job_i, t) -> (job_j, t+time_span)
                    final_time = self.T - time_span

                    # Define all the arcs in the computed range
                    for time in range(initial_time, final_time + 1):
                        self.arcs.append(tuple(["A1", job_i, time, job_j, time + time_span]))
                        arcs_counter = arcs_counter + 1

        return arcs_counter

    # NOTE: We compute A2, saving the results in the list self.arcs with the structure:
    #            self.arcs[0]="A2"
    #            self.arcs[1]="0"
    #            self.arcs[2]="t"
    #            self.arcs[3]="j"
    #            self.arcs[4]="t + s_oj + pj"
    #       where (0, t) is a node of O and (j, t + s_oj + pj) is a node of R
    def set_A2(self):
        arcs_counter = 0
        # For each job j, excluding the dummy job 0, compute all the arcs of type:
        #   (0, t) -> (j -> t + s_oj + pj) with the constraint t>=r_j
        for job in range(1, self.n_jobs + 1):

            # time_span = s_oj + pj
            time_span = self.setup_times[0][job] + self.processing_times[job]

            # Get the smaller t from the arcs (0, t) -> (job, t+time_span)
            release_date_j = self.release_dates[job]
            initial_time = max(0, release_date_j)  # Not needed, we let it uniformity with the code of A1

            # Get the largest t from the set of arcs of type: (0, t) -> (job, t+time_span)
            final_time = self.T - time_span

            # Define all the arcs in the computed range
            for time in range(initial_time, final_time + 1):
                self.arcs.append(tuple(["A2", 0, time, job, time + time_span]))
                arcs_counter = arcs_counter + 1

        return arcs_counter

    # NOTE: We compute A3, saving the results in the list self.arcs with the structure:
    #            self.arcs[0]="A3"
    #            self.arcs[1]="i"
    #            self.arcs[2]="t"
    #            self.arcs[3]="0"
    #            self.arcs[4]="T"
    #       where (i, t) is a node of R (and (0, T) is a node of O)
    def set_A3(self):
        arcs_counter = 0
        # For each job j, excluding the dummy job 0, create an arc that goes from every node (j, t) to the node (0, T)
        for job in range(1, self.n_jobs + 1):
            for time in self.R_as_matrix[job]:
                self.arcs.append(tuple(["A3", job, time, 0, self.T]))
                arcs_counter = arcs_counter + 1

        return arcs_counter

    # NOTE: We compute A4 saving, the results in the list self.arcs with the structure:
    #            self.arcs[0]="A4"
    #            self.arcs[1]="i"
    #            self.arcs[2]="t"
    #            self.arcs[3]="i"
    #            self.arcs[4]="t+1"
    #       where (i, t) and (i, t+1) are nodes of V = R U O
    def set_A4(self):
        arcs_counter = 0

        # First create all the arcs of the dummy job 0, i.e., the arcs of type (0, t) -> (0, t+1)
        for node in self.O:
            time = node[1]
            if time >= self.T:
                break
            else:
                next_time = self.O[time + 1][1]
                if time + 1 != next_time:
                    print(time, next_time)
                    raise Exception("Error in the parsing of matrix O")
                else:
                    self.arcs.append(tuple(["A4", 0, time, 0, time + 1]))
                    arcs_counter = arcs_counter + 1

        # Then, for each job j, excluding the dummy job 0, create all the arcs of type (j, t) -> (j, t+1)
        for job in range(1, self.n_jobs + 1):
            # Fixed the job, create all the arcs, starting from (j, s_bar_j + r_j + p_j)
            # Where, s_bar_j + r_j + p_j is the time stored in position 0 of the list R[job]
            for index, time in enumerate(self.R_as_matrix[job]):
                if time >= self.T:
                    break
                else:
                    next_time = self.R_as_matrix[job][index + 1]
                    # Check if the list R[job] is correctly ordered
                    if time + 1 != next_time:
                        print(time, next_time)
                        raise Exception("Error in the parsing of matrix R")
                    else:
                        self.arcs.append(tuple(["A4", job, time, job, time + 1]))
                        arcs_counter = arcs_counter + 1

        return arcs_counter

    def set_As_and_arcs(self):
        self.arcs = []

        n_arcs_A1 = self.set_A1()
        n_arcs_A2 = self.set_A2()
        n_arcs_A3 = self.set_A3()
        n_arcs_A4 = self.set_A4()

        t = 0
        self.range_A1 = range(t, n_arcs_A1)
        t = t + n_arcs_A1
        self.range_A2 = range(t, t + n_arcs_A2)
        t = t + n_arcs_A2
        self.range_A3 = range(t, t + n_arcs_A3)
        t = t + n_arcs_A3
        self.range_A4 = range(t, t + n_arcs_A4)
        t = t + n_arcs_A4
        self.range_arcs = range(0, t)
