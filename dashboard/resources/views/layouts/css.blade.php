<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
    .home-header {
        width: 100%;
        padding: 56px 16px 48px;
        text-align: center;
        background: linear-gradient(135deg, #0b1f4d 0%, #1b48a1 55%, #3b8beb 100%);
        color: #fff;
        box-shadow: 0 4px 18px rgba(11, 31, 77, .3);
    }

    .home-header {
        position: relative;
    }

    /* Login / utilizador no canto superior direito do cabeçalho */
    .home-auth {
        position: absolute;
        top: 16px;
        right: 16px;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .home-auth-user {
        font-size: .9rem;
        opacity: .9;
    }

    .home-title {
        margin: 0;
        font-size: clamp(2.2rem, 6vw, 4rem);
        font-weight: 800;
        letter-spacing: 1px;
        text-transform: uppercase;
        text-shadow: 0 3px 10px rgba(0, 0, 0, .25);
    }

    .home-subtitle {
        margin: 12px 0 0;
        font-size: clamp(1rem, 2.2vw, 1.3rem);
        font-weight: 400;
        letter-spacing: 3px;
        text-transform: uppercase;
        opacity: .9;
    }

    .home-subtitle::before,
    .home-subtitle::after {
        content: "";
        display: inline-block;
        width: 40px;
        height: 2px;
        margin: 0 14px;
        vertical-align: middle;
        background: rgba(255, 255, 255, .7);
    }

    .home-nav {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 12px;
        padding: 24px 16px;
    }

    .home-nav-btn {
        min-width: 200px;
        padding: 12px 28px;
        border: 2px solid #1b48a1;
        border-radius: 999px;
        background: #fff;
        color: #1b48a1;
        font-weight: 600;
        font-size: 1rem;
        letter-spacing: .3px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, .08);
        transition: background-color .2s, color .2s, transform .15s, box-shadow .2s;
    }

    .home-nav-btn:hover {
        background: #e8effb;
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(27, 72, 161, .2);
    }

    .home-nav-btn:focus-visible {
        outline: 3px solid rgba(27, 72, 161, .4);
        outline-offset: 2px;
    }

    .home-nav-btn.active {
        background: #1b48a1;
        color: #fff;
        box-shadow: 0 6px 14px rgba(27, 72, 161, .35);
    }

    .legend-group {
        margin-bottom: 6px;
        font-size: .8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .5px;
        color: #6c757d;
    }

    .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;
        font-size: .9rem;
    }

    .legend-icon {
        width: 24px;
        height: 24px;
        object-fit: contain;
        flex-shrink: 0;
    }

    .map-canvas {
        width: 100%;
        height: 500px;
    }

    /* Telefone/tablet: legenda passa para baixo do mapa, grupos lado a lado */
    @media (max-width: 991.98px) {
        .map-canvas {
            height: 380px;
        }

        .map-legend {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            column-gap: 16px;
        }

        .map-legend ul {
            margin-bottom: 8px !important;
        }
    }

    .stat-card {
        display: flex;
        align-items: center;
        gap: 16px;
        height: 100%;
        padding: 18px 20px;
        border: 1px solid #e6ebf3;
        border-left: 4px solid var(--stat-color);
        border-radius: 12px;
        background: #fff;
        box-shadow: 0 2px 8px rgba(11, 31, 77, .06);
        transition: transform .15s, box-shadow .2s;
    }

    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 18px rgba(11, 31, 77, .12);
    }

    .stat-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        width: 48px;
        height: 48px;
        border-radius: 12px;
        /* fundo = cor do cartão com transparência */
        background: color-mix(in srgb, var(--stat-color) 12%, transparent);
        color: var(--stat-color);
        font-size: 1.4rem;
    }

    .stat-value {
        font-size: 1.8rem;
        font-weight: 800;
        line-height: 1;
        color: #0b1f4d;
    }

    .stat-label {
        margin-top: 4px;
        font-size: .85rem;
        color: #6c757d;
    }

    /* Modal de resultado: caixas dos elementos por cima da imagem */
    .result-image {
        position: relative;
        display: inline-block;
        width: 100%;
    }

    .result-image img {
        width: 100%;
    }

    .result-box {
        position: absolute;
        border: 3px solid #3b8beb;
        border-radius: 4px;
        box-shadow: 0 0 0 1px rgba(0, 0, 0, .4);
    }

    .result-box span {
        position: absolute;
        bottom: 100%;
        left: -3px;
        padding: 1px 6px;
        border-radius: 4px 4px 0 0;
        background: #3b8beb;
        color: #fff;
        font-size: .75rem;
        white-space: nowrap;
    }

    @media (max-width: 576px) {
        .home-nav-btn {
            flex: 1 1 100%;
            min-width: 0;
        }
    }

    .map-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border: 2px solid #fff;
        border-radius: 50%;
        color: #fff;
        font-size: 16px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, .35);
    }

    .map-dot {
        width: 16px;
        height: 16px;
        border: 2px solid #fff;
        border-radius: 50%;
        box-shadow: 0 1px 4px rgba(0, 0, 0, .4);
    }

    /* CATÁLOGO: sidebar com scroll */
    .catalog-sidebar {
        display: flex;
        flex-direction: column;
        height: 70vh;
        /* altura fixa: o que não cabe faz scroll */
        min-height: 320px;
        border: 1px solid #e6ebf3;
        border-radius: 12px;
        background: #fff;
        box-shadow: 0 2px 8px rgba(11, 31, 77, .06);
        overflow: hidden;
    }

    .catalog-sidebar-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 16px;
        border-bottom: 1px solid #e6ebf3;
        font-weight: 700;
        color: #0b1f4d;
    }

    /* Filtros por cima da lista do catálogo */
    .catalog-filters {
        padding: 10px 12px;
        border-bottom: 1px solid #e6ebf3;
        background: #f8fafd;
    }

    .catalog-sidebar-list {
        flex: 1;
        overflow-y: auto;
        /* scroll só dentro da lista */
        padding: 6px;
    }

    .catalog-item {
        display: flex;
        align-items: center;
        gap: 12px;
        width: 100%;
        padding: 10px 12px;
        border: 0;
        border-radius: 8px;
        background: transparent;
        text-align: left;
        transition: background-color .15s;
    }

    .catalog-item:hover {
        background: #f1f5fc;
    }

    .catalog-item.active {
        background: #e8effb;
        box-shadow: inset 3px 0 0 #1b48a1;
    }

    .catalog-item-text {
        display: flex;
        flex-direction: column;
        min-width: 0;
        flex: 1;
    }

    .catalog-item-name {
        overflow: hidden;
        font-weight: 600;
        color: #0b1f4d;
        white-space: nowrap;
        text-overflow: ellipsis;
    }

    .catalog-item-confidence {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: .8rem;
        color: #6c757d;
    }

    .confidence-bar {
        flex: 1;
        max-width: 120px;
        height: 5px;
        border-radius: 3px;
        background: #e6ebf3;
        overflow: hidden;
    }

    .confidence-bar span {
        display: block;
        height: 100%;
        background: #1b48a1;
    }

    /* Painel do elemento selecionado: largura toda, mas baixo */
    .element-detail {
        font-size: .875rem;
    }

    .element-detail .card-header {
        padding: 8px 12px;
    }

    .element-detail-content {
        display: flex;
    }

    .element-detail-photo {
        flex: 0 0 38%;
        align-self: flex-start;
        /* foto inteira (sem cortar), para as bounding boxes ficarem no sítio certo */
    }

    [x-cloak] {
        display: none !important;
    }

    /* Mapa: popup do marcador com localização e foto */
    .map-popup-coords {
        margin: 2px 0 8px;
        font-size: .8rem;
    }

    .map-popup-photo {
        position: relative;
        line-height: 0;
    }

    .map-popup-photo img {
        display: block;
        width: 100%;
        height: auto;
        border-radius: 6px;
    }

    .map-popup-box {
        display: none; /* aparece quando a foto carrega e se sabe o tamanho */
        position: absolute;
        border: 2px solid #0d6efd;
        pointer-events: none;
    }

    .map-popup-credit {
        margin-top: 4px;
        font-size: .7rem;
        color: #6c757d;
    }

    /* Foto em grande com bounding boxes (abre ao clicar numa foto) */
    .photo-lightbox {
        position: fixed;
        inset: 0;
        z-index: 2100; /* por cima do modal e do ecrã de espera */
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 16px;
        background: rgba(0, 0, 0, .85);
        cursor: zoom-out;
    }

    .photo-lightbox-frame {
        position: relative;
        line-height: 0;
        cursor: default;
    }

    .photo-lightbox-frame img {
        display: block;
        max-width: calc(100vw - 32px);
        max-height: calc(100vh - 32px);
        border-radius: 6px;
    }

    .photo-lightbox-box {
        position: absolute;
        border: 3px solid #0d6efd;
        pointer-events: none;
    }

    .photo-lightbox-box span {
        position: absolute;
        bottom: 100%;
        left: -3px;
        padding: 2px 6px;
        font-size: .8rem;
        line-height: 1.3;
        color: #fff;
        white-space: nowrap;
    }

    .photo-lightbox-close {
        position: absolute;
        top: 16px;
        right: 16px;
    }

    /* Experimenta: ecrã de espera com o fundo desfocado */
    .processing-overlay {
        position: fixed;
        inset: 0;
        z-index: 2000; /* por cima do modal e do mapa */
        align-items: center;
        justify-content: center;
        padding: 16px;
        background: rgba(255, 255, 255, .45);
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
    }

    .processing-box {
        max-width: 360px;
        padding: 24px 28px;
        text-align: center;
        background: #fff;
        border-radius: 12px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, .15);
    }

    .element-detail .card-body {
        flex: 1;
        min-width: 0;
        padding: 12px 16px;
    }

    .element-detail dd {
        margin-bottom: 4px;
    }

    /* Ecrã pequeno: foto em cima, detalhes em baixo */
    @media (max-width: 575px) {
        .element-detail-content {
            flex-direction: column;
        }

        .element-detail-photo {
            flex-basis: auto;
        }
    }

    /* O detalhe acompanha o scroll da página */
    @media (min-width: 768px) {
        .catalog-detail>.card {
            position: sticky;
            top: 16px;
        }
    }
</style>
