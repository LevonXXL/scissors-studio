const catalogueNode = document.getElementById('review-unlinked-services');
const catalogue = catalogueNode ? JSON.parse(catalogueNode.textContent) : {};

const normalizeServiceTitle = (value) => value
  .normalize('NFKC')
  .toLocaleLowerCase('ru')
  .replaceAll('ё', 'е')
  .replace(/\s+/g, ' ')
  .trim();

const indexedCatalogue = Object.fromEntries(
  Object.entries(catalogue).map(([salonId, services]) => [
    salonId,
    services.map((service) => ({ ...service, searchTitle: normalizeServiceTitle(service.title) })),
  ]),
);

document.getElementById('review-select-ready')?.addEventListener('click', () => {
  document.querySelectorAll('.review-ready-checkbox').forEach((checkbox) => {
    checkbox.checked = true;
  });
});

document.getElementById('review-clear-ready')?.addEventListener('click', () => {
  document.querySelectorAll('.review-ready-checkbox').forEach((checkbox) => {
    checkbox.checked = false;
  });
});

document.querySelectorAll('.review-service-picker').forEach((picker) => {
  const form = picker.closest('form');
  const input = picker.querySelector('.review-search');
  const results = picker.querySelector('.review-search-results');
  const hint = picker.querySelector('.review-search-hint');
  const picked = picker.querySelector('.review-picked');
  const services = indexedCatalogue[picker.dataset.salonId] || [];

  const showResults = () => {
    const query = normalizeServiceTitle(input.value);
    results.replaceChildren();
    if (query.length < 3) {
      hint.textContent = 'Введите минимум 3 символа для поиска.';
      return;
    }

    const alreadyListed = new Set(
      [...form.querySelectorAll('input[name="target_id"]')].map((field) => field.value),
    );
    const matches = services.filter((service) =>
      service.searchTitle.includes(query) && !alreadyListed.has(String(service.id)),
    ).slice(0, 12);
    hint.textContent = matches.length
      ? 'Выберите услугу из списка. Показаны первые 12 совпадений.'
      : 'Подходящих свободных услуг в этом салоне нет.';
    matches.forEach((service) => {
      const item = document.createElement('li');
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = `#${service.id} ${service.title}`;
      button.addEventListener('click', () => {
        const field = document.createElement('input');
        field.type = 'hidden';
        field.name = 'target_id';
        field.value = String(service.id);
        form.append(field);

        const chip = document.createElement('button');
        chip.type = 'button';
        chip.textContent = `${service.title} ×`;
        chip.setAttribute('aria-label', `Убрать услугу ${service.title}`);
        chip.addEventListener('click', () => {
          field.remove();
          chip.remove();
          showResults();
        });
        picked.append(chip);
        input.value = '';
        showResults();
        input.focus();
      });
      item.append(button);
      results.append(item);
    });
  };

  input.addEventListener('input', showResults);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      results.querySelector('button')?.click();
    }
  });
});
