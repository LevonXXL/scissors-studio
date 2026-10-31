export interface MessengerLink {
  label: string;
  icon: string;
  href: string;
}

// Shared by the navigation and feedback dialog.
export const messengerLinks: MessengerLink[] = [
  {
    label: 'Telegram',
    icon: '/contacts/tg-64.png',
    href: 'https://t.me/+79260717163',
  },
  {
    label: 'WhatsApp',
    icon: '/contacts/whatsapp-64.png',
    href: 'https://wa.me/79260717163',
  },
  {
    label: 'MAX',
    icon: '/contacts/max-logo-32x32.png',
    href: 'https://max.ru/u/f9LHodD0cOIEo5BBirO7N1w9G-wWVixUEGYYGtWQie2w14gY6w7oV7_DEnM',
  },
];
