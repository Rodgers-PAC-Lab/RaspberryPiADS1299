import time
import datetime
import numpy as np
import pandas
import threading
import queue
import os


# This is a class that we use to simulate DRDY
# We use it to call a callback every N seconds
# https://stackoverflow.com/questions/12435211/threading-timer-repeat-function-every-n-seconds
class RepeatTimer(threading.Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)

# This is where chunks are written
data_directory = os.path.expanduser('~/data')
if not os.path.exists(data_directory):
    os.mkdir(data_directory)

# This is where diagnostics are written
diag_directory = os.path.expanduser('~/diagnostics')
if not os.path.exists(diag_directory):
    os.mkdir(diag_directory)

# Callback
def acquire_data():
    results = bytearray(23)
    q.put_nowait(results)
    sample_read_times.append(datetime.datetime.now())

# This timer simulates DRDY
# Every 1 second, it will call acquire_data
# TODO: Replace this timer with a pigpio callback
t = RepeatTimer(.0001, acquire_data)
t.start()


## Main loop
save_times_l = []
sample_read_times = []

q = queue.Queue(maxsize=20000)
print("listening")


# Remove the flag
if os.path.exists('stop'):
    os.remove('stop')

# Keep doing this until the user presses CTRL+C
try:
    while not os.path.exists('stop'):
        # Check if the queue is long enough to write to disk
        #print("got into while True")
        if q.qsize() > 4000:
            # Get all of the data out of the queue
            data_to_write = []
            while True:
                try:
                    data = q.get_nowait()
                    #print(data)
                except queue.Empty:
                    break

                data_to_write.append(data)

            # Here is where we would interpret the bytes
            # using struct.unpack or whatever
            # For now just concatenate
            concatted = np.concatenate(
                data_to_write, dtype=np.uint8, casting='unsafe')

            # Write the concatenated/interpreted data to disk
            # TODO: instead of always using the same filename, we
            # would use a dated filename
            #print('writing to disk')

            # Generate a filename
            time_now = datetime.datetime.now()
            time_now_string = time_now.strftime('%Y%m%d_%H%M%S%f')

            # Save the data
            print('Saved chunk at {}'.format(time_now))
            save_times_l.append(time_now)
            filename = os.path.join(data_directory,
                'chunk_{}'.format(time_now_string))
            np.save(filename, concatted)

        # This sleep just keeps this while-loop from running too
        # frequently
        time.sleep(.1)

except:
    raise

finally:
    # Stop the timer from adding more data to the queue
    # Replace this with a cancellation of the pigpio callback
    t.cancel()

# Get result
print("stopping")

# Extract the time of the sample reads
sample_read_times_arr = np.array(sample_read_times)

# Save the diagnostics
#~ np.save(os.path.join(diag_directory, 'sample_read_times_arr'), sample_read_times_arr)
#~ np.save(os.path.join(diag_directory, 'save_times_arr'), np.array(save_times_l))

