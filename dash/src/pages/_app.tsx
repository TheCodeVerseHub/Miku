import '@/styles/globals.css'
import type { AppProps } from 'next/app'
import { SessionProvider } from 'next-auth/react'
import { SWRConfig } from 'swr'

export default function App({ Component, pageProps: { session, ...pageProps } }: AppProps) {
  return (
    <SessionProvider session={session}>
      <SWRConfig
        value={{
          fetcher: (url: string) => fetch(url).then((res) => {
            if (!res.ok) throw new Error('API request failed')
            return res.json()
          }),
          revalidateOnFocus: false,
          revalidateOnReconnect: false,
          dedupingInterval: 30000, // 30 seconds
          errorRetryCount: 2,
          errorRetryInterval: 2000,
          shouldRetryOnError: true,
          onError: (error, key) => {
            console.error(`SWR Error for ${key}:`, error)
          },
        }}
      >
        <Component {...pageProps} />
      </SWRConfig>
    </SessionProvider>
  )
}

