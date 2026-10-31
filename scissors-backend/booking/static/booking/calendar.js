const MASTER_DAY_FIRST_HOUR = 7;
const MASTER_DAY_LAST_HOUR = 24;
const MASTER_DAY_HOUR_HEIGHT = 64;

function masterDayMinutes(iso) {
  const time = iso?.slice(11, 16);
  if (!time) return null;
  const [hours, minutes] = time.split(':').map(Number);
  return hours * 60 + minutes;
}

function masterDayPositions(events, date) {
  const firstMinute = MASTER_DAY_FIRST_HOUR * 60;
  const lastMinute = MASTER_DAY_LAST_HOUR * 60;
  const positioned = events.map((event) => {
    const startStr = event.startStr;
    const endStr = event.endStr;
    const start = startStr.slice(0, 10) < date ? 0 : masterDayMinutes(startStr);
    const end = endStr
      ? (endStr.slice(0, 10) > date ? 24 * 60 : masterDayMinutes(endStr))
      : start + 30;
    return {
      event,
      start: Math.max(firstMinute, start),
      end: Math.min(lastMinute, end),
      lane: 0,
      lanes: 1,
    };
  }).filter((item) => item.end > item.start)
    .sort((a, b) => a.start - b.start || a.end - b.end);

  let cluster = [];
  let occupied = [];
  const finishCluster = () => {
    const lanes = Math.max(1, ...cluster.map((item) => item.lane + 1));
    cluster.forEach((item) => { item.lanes = lanes; });
    cluster = [];
    occupied = [];
  };
  positioned.forEach((item) => {
    occupied = occupied.filter((active) => active.end > item.start);
    if (!occupied.length && cluster.length) finishCluster();
    const taken = new Set(occupied.map((active) => active.lane));
    while (taken.has(item.lane)) item.lane += 1;
    occupied.push(item);
    cluster.push(item);
  });
  if (cluster.length) finishCluster();
  return positioned;
}

function renderMasterDay(element, mastersBySalon, salonId, date, events, openBooking) {
  element.replaceChildren();
  const dayEvents = events.filter((event) =>
    event.startStr.slice(0, 10) <= date &&
    (event.endStr
      ? event.endStr.slice(0, 10) >= date
      : event.startStr.slice(0, 10) === date));
  const columns = [...(mastersBySalon[salonId] || [])];
  const known = new Set(columns.map((master) => String(master.id)));
  dayEvents.forEach((event) => {
    const id = event.extendedProps.master_id;
    const key = id == null ? 'unassigned' : String(id);
    if (!known.has(key)) {
      columns.push({ id: key, name: event.extendedProps.master_name || 'Без мастера' });
      known.add(key);
    }
  });
  if (!columns.length) {
    const empty = document.createElement('p');
    empty.className = 'booking-master-day__empty';
    empty.textContent = 'В этом филиале нет мастеров для отображения.';
    element.append(empty);
    return;
  }

  const scroll = document.createElement('div');
  scroll.className = 'booking-master-day__scroll';
  const board = document.createElement('div');
  board.className = 'booking-master-day__board';
  board.style.gridTemplateColumns = `72px repeat(${columns.length}, minmax(190px, 1fr))`;
  board.style.minWidth = `${72 + columns.length * 190}px`;
  board.style.setProperty('--booking-day-height',
    `${(MASTER_DAY_LAST_HOUR - MASTER_DAY_FIRST_HOUR) * MASTER_DAY_HOUR_HEIGHT}px`);

  const timeHeading = document.createElement('div');
  timeHeading.className = 'booking-master-day__time-heading';
  timeHeading.textContent = 'Время';
  board.append(timeHeading);
  columns.forEach((master) => {
    const heading = document.createElement('div');
    heading.className = 'booking-master-day__master-heading';
    heading.textContent = master.name;
    board.append(heading);
  });

  const axis = document.createElement('div');
  axis.className = 'booking-master-day__axis';
  for (let hour = MASTER_DAY_FIRST_HOUR; hour < MASTER_DAY_LAST_HOUR; hour += 1) {
    const label = document.createElement('span');
    label.style.top = `${(hour - MASTER_DAY_FIRST_HOUR) * MASTER_DAY_HOUR_HEIGHT}px`;
    label.textContent = `${String(hour).padStart(2, '0')}:00`;
    axis.append(label);
  }
  board.append(axis);

  columns.forEach((master) => {
    const column = document.createElement('div');
    column.className = 'booking-master-day__column';
    column.setAttribute('aria-label', master.name);
    const masterEvents = dayEvents.filter((event) => {
      const id = event.extendedProps.master_id;
      return String(id == null ? 'unassigned' : id) === String(master.id);
    });
    masterDayPositions(masterEvents, date).forEach((item) => {
      const booking = document.createElement('button');
      booking.type = 'button';
      booking.className = `booking-master-day__event ${item.event.classNames.join(' ')}`;
      booking.style.top = `${(item.start / 60 - MASTER_DAY_FIRST_HOUR) * MASTER_DAY_HOUR_HEIGHT}px`;
      booking.style.height = `${Math.max(22, (item.end - item.start) / 60 * MASTER_DAY_HOUR_HEIGHT)}px`;
      booking.style.left = `calc(${item.lane * 100 / item.lanes}% + 2px)`;
      booking.style.width = `calc(${100 / item.lanes}% - 4px)`;
      const time = document.createElement('strong');
      time.textContent = `${item.event.startStr.slice(11, 16)}–${item.event.endStr?.slice(11, 16) || '…'}`;
      const title = document.createElement('span');
      title.textContent = item.event.extendedProps.client_name || item.event.extendedProps.service || 'Занято';
      booking.append(time, title);
      if (item.event.extendedProps.service && item.event.extendedProps.client_name) {
        const service = document.createElement('span');
        service.textContent = item.event.extendedProps.service;
        booking.append(service);
      }
      booking.title = item.event.title;
      booking.addEventListener('click', () => openBooking(item.event.url));
      column.append(booking);
    });
    board.append(column);
  });
  scroll.append(board);
  element.append(scroll);
}

document.addEventListener('DOMContentLoaded', () => {
  const calendarElement = document.getElementById('booking-calendar');
  if (!calendarElement) return;

  const salonSelect = document.getElementById('booking-salon');
  const errorElement = document.getElementById('booking-calendar-error');
  const dialog = document.getElementById('booking-calendar-dialog');
  const frame = document.getElementById('booking-calendar-frame');
  const fullLink = document.getElementById('booking-open-full');
  const closeButton = document.getElementById('booking-close-dialog');
  const masterDay = document.getElementById('booking-master-day');
  const mastersBySalon = JSON.parse(document.getElementById('booking-calendar-masters')?.textContent || '{}');
  let dayDate = '';
  let dayActive = false;
  let currentEvents = [];

  const openBooking = (url) => {
    fullLink.href = url;
    frame.src = `${url}?calendar_modal=1`;
    dialog.showModal();
  };
  const updateMasterDay = () => {
    if (dayActive && dayDate) {
      renderMasterDay(masterDay, mastersBySalon, salonSelect.value, dayDate, currentEvents, openBooking);
    }
  };

  if (!window.FullCalendar) {
    errorElement.textContent = 'Календарь не загрузился. Обновите страницу.';
    errorElement.hidden = false;
    return;
  }

  const calendar = new FullCalendar.Calendar(calendarElement, {
    locale: 'ru',
    timeZone: 'Europe/Moscow',
    initialView: window.innerWidth < 700 ? 'timeGridDay' : 'timeGridWeek',
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'dayGridMonth,timeGridWeek,timeGridDay',
    },
    height: 'auto',
    nowIndicator: true,
    scrollTime: '09:00:00',
    slotMinTime: '07:00:00',
    slotMaxTime: '24:00:00',
    dayMaxEvents: true,
    editable: false,
    selectable: false,
    datesSet: (info) => {
      dayActive = info.view.type === 'timeGridDay';
      dayDate = info.startStr.slice(0, 10);
      calendarElement.classList.toggle('booking-calendar-day-mode', dayActive);
      masterDay.hidden = !dayActive;
      updateMasterDay();
    },
    eventsSet: (events) => {
      currentEvents = events;
      updateMasterDay();
    },
    events: {
      url: calendarElement.dataset.eventsUrl,
      extraParams: () => ({ salon: salonSelect.value }),
    },
    eventSourceSuccess: (data) => {
      errorElement.hidden = true;
      return data;
    },
    eventSourceFailure: () => {
      errorElement.textContent = 'Не удалось загрузить записи. Проверьте доступ и повторите попытку.';
      errorElement.hidden = false;
    },
    eventDidMount: (info) => {
      const details = info.event.extendedProps;
      info.el.title = [info.event.title, details.salon, details.status, details.service]
        .filter(Boolean).join(' · ');
    },
    eventClick: (info) => {
      info.jsEvent.preventDefault();
      openBooking(info.event.url);
    },
  });

  calendar.render();
  salonSelect.addEventListener('change', () => {
    currentEvents = [];
    updateMasterDay();
    calendar.refetchEvents();
  });
  closeButton.addEventListener('click', () => dialog.close());
  document.querySelectorAll('[data-booking-modal]').forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      const modalUrl = new URL(link.href);
      if (link.hasAttribute('data-booking-create')) {
        modalUrl.searchParams.set('salon', salonSelect.value);
      }
      const fullUrl = new URL(modalUrl);
      fullUrl.searchParams.delete('calendar_modal');
      fullLink.href = fullUrl.href;
      frame.src = modalUrl.href;
      dialog.showModal();
    });
  });
  dialog.addEventListener('close', () => frame.removeAttribute('src'));
  window.addEventListener('message', (event) => {
    if (event.origin !== window.location.origin || event.source !== frame.contentWindow) return;
    if (event.data?.type !== 'scissors-booking-saved') return;
    dialog.close();
    calendar.refetchEvents();
  });
});
