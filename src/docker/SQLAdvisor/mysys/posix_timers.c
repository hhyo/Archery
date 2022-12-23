/* Copyright (c) 2012, Twitter, Inc. All rights reserved.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; version 2 of the License.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License along
   with this program; if not, write to the Free Software Foundation, Inc.,
   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA. */

#include "my_timer.h"       /* my_timer_t */
#include "my_pthread.h"     /* my_thread_init, my_thread_end */
#include "m_string.h"         /* memset */
#include <sys/syscall.h>    /* SYS_gettid */

#ifndef sigev_notify_thread_id
#define sigev_notify_thread_id   _sigev_un._tid
#endif

#define MY_TIMER_EVENT_SIGNO  (SIGRTMIN)
#define MY_TIMER_KILL_SIGNO   (SIGRTMIN+1)

/* Timer thread object. */
static pthread_t thread;

/* Timer thread ID (TID). */
static pid_t thread_id;

/**
  Timer expiration notification function.

  @param  sigev_value   Signal (notification) value.

  @remark The notification function is usually run in a helper thread
          and is called each time the timer expires.
*/

static void
timer_notify_function(sigval_t sigev_value)
{
  my_timer_t *timer= sigev_value.sival_ptr;
  timer->notify_function(timer);
}


/**
  Timer expiration notification thread.

  @param  arg   Barrier object.
*/

static void *
timer_notify_thread(void *arg)
{
  sigset_t set;
  siginfo_t info;
  pthread_barrier_t *barrier= arg;

  my_thread_init();

  sigemptyset(&set);
  sigaddset(&set, MY_TIMER_EVENT_SIGNO);
  sigaddset(&set, MY_TIMER_KILL_SIGNO);

  /* Get the thread ID of the current thread. */
  thread_id= (pid_t) syscall(SYS_gettid);

  /* Wake up parent thread, thread_id is available. */
  pthread_barrier_wait(barrier);

  while (1)
  {
    if (sigwaitinfo(&set, &info) < 0)
      continue;

    if (info.si_signo == MY_TIMER_EVENT_SIGNO)
      timer_notify_function(info.si_value);
    else if (info.si_signo == MY_TIMER_KILL_SIGNO)
      break;
  }

  my_thread_end();

  return NULL;
}


/**
  Create a helper thread to dispatch timer expiration notifications.

  @return On success, 0. On error, -1 is returned.
*/

static int
start_helper_thread(void)
{
  pthread_barrier_t barrier;

  if (pthread_barrier_init(&barrier, NULL, 2))
    return -1;

  if (pthread_create(&thread, NULL, timer_notify_thread, &barrier))
    return -1;

  pthread_barrier_wait(&barrier);
  pthread_barrier_destroy(&barrier);

  return 0;
}


/**
  Initialize internal components.

  @return On success, 0.
          On error, -1 is returned, and errno is set to indicate the error.
*/

int
my_os_timer_init_ext(void)
{
  int rc;
  sigset_t set, old_set;

  if (sigfillset(&set))
    return -1;

  /*
    Temporarily block all signals. New thread will inherit signal
    mask of the current thread.
  */
  if (pthread_sigmask(SIG_BLOCK, &set, &old_set))
    return -1;

  /* Create a helper thread. */
  rc= start_helper_thread();

  /* Restore the signal mask. */
  pthread_sigmask(SIG_SETMASK, &old_set, NULL);

  return rc;
}


/**
  Release any resources that were allocated as part of initialization.
*/

void
my_os_timer_deinit(void)
{
  /* Kill helper thread. */
  pthread_kill(thread, MY_TIMER_KILL_SIGNO);

  /* Wait for helper thread termination. */
  pthread_join(thread, NULL);
}


/**
  Create a timer object.

  @param  timer   Location where the timer ID is returned.

  @return On success, 0.
          On error, -1 is returned, and errno is set to indicate the error.
*/

int
my_os_timer_create(my_timer_t *timer)
{
  struct sigevent sigev;

  memset(&sigev, 0, sizeof(sigev));

  sigev.sigev_value.sival_ptr= timer;
  sigev.sigev_signo= MY_TIMER_EVENT_SIGNO;
  sigev.sigev_notify= SIGEV_SIGNAL | SIGEV_THREAD_ID;
  sigev.sigev_notify_thread_id= thread_id;

  return timer_create(CLOCK_MONOTONIC, &sigev, &timer->id);
}


/**
  Set the time until the next expiration of the timer.

  @param  timer   Timer object.
  @param  time    Amount of time (in milliseconds) before the timer expires.

  @return On success, 0.
          On error, -1 is returned, and errno is set to indicate the error.
*/

int
my_os_timer_set(my_timer_t *timer, unsigned long time)
{
  const struct itimerspec spec= {
    .it_interval= {.tv_sec= 0, .tv_nsec= 0},
    .it_value= {.tv_sec= time / 1000,
                .tv_nsec= (time % 1000) * 1000000}
  };

  return timer_settime(timer->id, 0, &spec, NULL);
}


/**
  Reset the time until the next expiration of the timer.

  @param  timer   Timer object.
  @param  state   The state of the timer at the time of cancellation, either
                  signaled (false) or nonsignaled (true).

  @return On success, 0.
          On error, -1 is returned, and errno is set to indicate the error.
*/

int
my_os_timer_reset(my_timer_t *timer, int *state)
{
  int status;
  struct itimerspec old_spec;

  /* A zeroed initial expiration value disarms the timer. */
  const struct timespec zero_time= { .tv_sec= 0, .tv_nsec= 0 };
  const struct itimerspec zero_spec= { .it_value= zero_time };

  /*
    timer_settime returns the amount of time before the timer
    would have expired or zero if the timer was disarmed.
  */
  if (! (status= timer_settime(timer->id, 0, &zero_spec, &old_spec)))
    *state= (old_spec.it_value.tv_sec || old_spec.it_value.tv_nsec);

  return status;
}


/**
  Delete a timer object.

  @param  timer   Timer object.
*/

void
my_os_timer_delete(my_timer_t *timer)
{
  timer_delete(timer->id);
}

