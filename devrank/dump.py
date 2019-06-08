import dill as pickle
import queue

users_already_done = set()
users_to_process = queue.Queue()
repos_already_done = set()
repos_to_process = queue.Queue()
orphans_to_process = []

with open('users_already_done', 'wb') as outfile:
    pickle.dump(users_already_done, outfile)
with open('users_to_process', 'wb') as outfile:
    pickle.dump(users_to_process, outfile)
with open('repos_already_done', 'wb') as outfile:
    pickle.dump(repos_already_done, outfile)
with open('repos_to_process', 'wb') as outfile:
    pickle.dump(repos_to_process, outfile)
import dill as pickle
with open('orphans_to_process', 'wb') as outfile:
    pickle.dump(orphans_to_process, outfile)