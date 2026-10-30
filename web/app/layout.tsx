import './globals.css';
export const metadata = { title:'My Intelligence', description:'Your private intelligence desk', manifest:'/manifest.webmanifest' };
export default function Layout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
