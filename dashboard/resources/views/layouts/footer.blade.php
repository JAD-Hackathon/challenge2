<style>
    body {
        min-height: 100vh;
        display: flex;
        flex-direction: column;
    }

    .site-footer {
        margin-top: auto;
        padding: 28px 16px;
        background: linear-gradient(135deg, #0b1f4d 0%, #1b48a1 55%, #3b8beb 100%);
        color: rgba(255, 255, 255, .85);
        text-align: center;
        font-size: .95rem;
        box-shadow: 0 -4px 18px rgba(11, 31, 77, .2);
    }

    .site-footer-title {
        margin: 0 0 10px;
        color: #fff;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    .site-footer-authors {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 8px;
        margin: 0 0 14px;
        padding: 0;
        list-style: none;
    }

    .site-footer-authors li {
        padding: 4px 14px;
        border: 1px solid rgba(255, 255, 255, .35);
        border-radius: 999px;
        background: rgba(255, 255, 255, .08);
        color: #fff;
    }

    .site-footer-copy {
        margin: 0;
        font-size: .8rem;
        opacity: .7;
    }
</style>

<footer class="site-footer">
    <p class="site-footer-title">Challenge 2 · Hackathon Aveiro 2026</p>
    <p class="mb-2">Desenvolvido por</p>
    <ul class="site-footer-authors">
        <li>André Montoito</li>
        <li>Dmytro Shcherbynskyi</li>
        <li>João Matias</li>
    </ul>
    <p class="site-footer-copy">&copy; {{ date('Y') }} · Todos os direitos reservados</p>
</footer>
