import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');

  console.log(
    `Current environment: ${mode}, API base URL: ${env.VITE_API_BASE_URL}`
  );

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      host: '0.0.0.0',
      allowedHosts: ['localhost', 'lmeterx', '127.0.0.1'],
      cors: true,
    },
    define: {
      'process.env': JSON.stringify(env),
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(
        env.VITE_API_BASE_URL
      ),
    },
    build: {
      sourcemap: false,
      assetsDir: 'assets',
      outDir: 'dist',
      rollupOptions: {
        output: {
          entryFileNames: 'assets/[name].[hash].js',
          chunkFileNames: 'assets/[name].[hash].js',
          assetFileNames: 'assets/[name].[hash].[ext]',
        },
      },
    },
    envDir: './',
    base: '/',
    publicDir: 'public',
  };
});
