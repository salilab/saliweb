class InvalidState(Exception):
    """Exception raised for invalid job states"""
    pass

class JobState(object):
    """Simple state machine for jobs"""
    __valid_states = ['INCOMING', 'PREPROCESSING', 'RUNNING',
                      'POSTPROCESSING', 'COMPLETED', 'FAILED',
                      'EXPIRED', 'ARCHIVED']
    __valid_transitions = [['INCOMING', 'PREPROCESSING'],
                           ['PREPROCESSING', 'RUNNING'],
                           ['RUNNING', 'POSTPROCESSING'],
                           ['POSTPROCESSING', 'COMPLETED'],
                           ['COMPLETED', 'ARCHIVED'],
                           ['ARCHIVED', 'EXPIRED'],
                           ['FAILED', 'INCOMING']]
    def __init__(self, state):
        if state in self.__valid_states:
            self.__state = state
        else:
            raise InvalidState("%s is not in %s" \
                               % (state, str(self.__valid_states)))
    def __str__(self):
        return "<JobState %s>" % self.get()
    def get(self):
        """Get current state, as a string."""
        return self.__state
    def get_valid_states(self):
        return __valid_states[:]
    def transition(self, newstate):
        """Change state to `newstate`. Raises an InvalidState exception if the
           new state is not valid."""
        tran = [self.__state, newstate]
        if newstate == 'FAILED' or tran in self.__valid_transitions:
            self.__state = newstate
        else:
            raise InvalidState("Cannot transition from %s to %s" \
                               % (self.__state, newstate))
