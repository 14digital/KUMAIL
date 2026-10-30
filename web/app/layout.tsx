import './globals.css';
export const metadata = { title:'KUMAIL', description:'Your personal listening intelligence assistant', manifest:'/manifest.webmanifest' };
export default function Layout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
