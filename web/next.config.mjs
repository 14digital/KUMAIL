/** @type {import('next').NextConfig} */
const config = {
  poweredByHeader: false,
  async rewrites() { return [{source:'/api/:path*',destination:(process.env.API_URL || 'http://127.0.0.1:8000')+'/api/:path*'}]; },
  async headers() { return [{ source:'/:path*', headers:[{key:'X-Content-Type-Options',value:'nosniff'},{key:'Referrer-Policy',value:'no-referrer'},{key:'X-Frame-Options',value:'DENY'}]}]; }
};
export default config;
