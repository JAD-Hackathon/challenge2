
<!doctype html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <!-- CSRF Token -->
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <meta name="robots" content="noindex, nofollow">

        <title>@yield('title') | CHALANGE 2 HACKTHON AVEIRO 2026</title>
    

    <!-- Fonts -->
    <link rel="dns-prefetch" href="//fonts.bunny.net">
    <link href="https://fonts.bunny.net/css?family=Nunito" rel="stylesheet">

    <link rel="shortcut icon" href="{{ URL::asset('build/resources/imagens/logo.png') }}">

    @vite(['resources/sass/app.scss', 'resources/js/app.js'])
    @include('layouts.head-css')
    @livewireStyles
    @yield('css')
</head>
<body data-bs-spy="scroll">
    @yield('content')

    @include('layouts.footer')

    <!-- JAVASCRIPT -->
    @livewireScripts
    @include('layouts.vendor-scripts')
    @stack('scripts')
</body>
</html>
