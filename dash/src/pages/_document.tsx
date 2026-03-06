import { Html, Head, Main, NextScript } from 'next/document'

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <link rel="icon" href="/favicon.ico" />
        <meta name="description" content="Miku Discord Leveling Bot Dashboard" />
      </Head>
      <body className="bg-discord-dark text-white">
        <Main />
        <NextScript />
      </body>
    </Html>
  )
}
