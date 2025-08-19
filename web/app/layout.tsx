import { UserProvider } from '@auth0/nextjs-auth0/client';
import 'bootstrap/dist/css/bootstrap.min.css';
import './globals.css';

export const metadata = {
  title: 'Itqan CMS',
  description: 'Quranic Content Management System',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body>
        <UserProvider>
          {children}
        </UserProvider>
      </body>
    </html>
  );
}
