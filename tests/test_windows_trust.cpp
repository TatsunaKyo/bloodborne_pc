// windows_trust.h: the ISRG roots the port carries and Windows' check of the server's whole chain.
// Offline: the four roots read and are the ones letsencrypt.org publishes (SHA-256).
// Online (skipped with BB_TEST_OFFLINE=1): game.supermedo.com, whose Let's Encrypt chain runs
// YE1 -> Root YE -> ISRG Root X2 -> ISRG Root X1, verifies with the port's roots alone; with roots
// that don't fit it OpenSSL refuses, Windows gets the whole chain and accepts it, but not for
// another host name; and the game's own setup (TrustWindowsRoots) connects.
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "windows_trust.h"

namespace {

const char* kServer = "https://game.supermedo.com:20443";
const char* kPath = "/bb-eu/ss.info";

std::string Hex(const unsigned char* data, unsigned len) {
    static const char digits[] = "0123456789ABCDEF";
    std::string out;
    for (unsigned i = 0; i < len; i++) {
        out += digits[data[i] >> 4];
        out += digits[data[i] & 15];
    }
    return out;
}

void CheckBundledRoots() {
    const struct {
        const char* name;
        const char* sha256;
    } expected[] = {
        {"ISRG Root X1", "96BCEC06264976F37460779ACF28C5A7CFE8A3C0AAE11A8FFCEE05C0BDDF08C6"},
        {"ISRG Root X2", "69729B8E15A86EFC177A57AFB7171DFC64ADD28C2FCA8CF1507E34453CCB1470"},
        {"Root YE", "E14FFCAD5B0025731006CAA43A121A22D8E9700F4FB9CF852F02A708AA5D5666"},
        {"Root YR", "E57B7E6F150C419102E8D5C055729FF967B9D1A829BF00CEC89CA604EBF4A86F"},
    };
    BIO* bio = BIO_new_mem_buf(bbnet::kBundledRoots, -1);
    int n = 0;
    while (X509* cert = PEM_read_bio_X509(bio, nullptr, nullptr, nullptr)) {
        assert(n < 4);
        unsigned char digest[EVP_MAX_MD_SIZE];
        unsigned len = 0;
        X509_digest(cert, EVP_sha256(), digest, &len);
        char cn[64] = {};
        X509_NAME_get_text_by_NID(X509_get_subject_name(cert), NID_commonName, cn, sizeof(cn));
        std::printf("root %d: %s %s\n", n, cn, Hex(digest, len).c_str());
        assert(std::strcmp(cn, expected[n].name) == 0);
        assert(Hex(digest, len) == expected[n].sha256);
        assert(X509_check_issued(cert, cert) == X509_V_OK); // self-signed
        X509_free(cert);
        n++;
    }
    BIO_free(bio);
    ERR_clear_error();
    assert(n == 4);
    X509_STORE* store = bbnet::BundledRootStore();
    assert(store);
    X509_STORE_free(store);
}

void CheckOnline() {
    {
        // The port's roots alone (no Windows store: a PEM store replaces it)
        httplib::SSLClient cli("game.supermedo.com", 20443);
        cli.load_ca_cert_store(bbnet::kBundledRoots, std::strlen(bbnet::kBundledRoots));
        cli.enable_server_certificate_verification(true);
        auto res = cli.Get(kPath);
        std::printf("port's roots alone: %s\n", res ? std::to_string(res->status).c_str() : httplib::to_string(res.error()).c_str());
        assert(res && res->status == 200);
    }
#ifdef _WIN32
    // Roots that don't fit (Root YR alone, for RSA chains): OpenSSL refuses, Windows decides
    std::string yr = bbnet::kBundledRoots;
    yr = yr.substr(yr.rfind("-----BEGIN CERTIFICATE-----"));
    for (const char* host : {"game.supermedo.com", "example.com"}) {
        httplib::SSLClient cli("game.supermedo.com", 20443); // its PEM store replaces Windows' one
        cli.load_ca_cert_store(yr.c_str(), yr.size());
        cli.enable_server_certificate_verification(true);
        bool asked = false, accepted = false;
        uint64_t error = 0;
        cli.set_session_verifier([&](httplib::tls::session_t session) {
            assert(httplib::tls::get_verify_result(session) != 0); // OpenSSL refused
            asked = true;
            accepted = bbnet::VerifyChainWithWindows(static_cast<SSL*>(session), host, error);
            return accepted ? httplib::SSLVerifierResponse::CertificateAccepted
                            : httplib::SSLVerifierResponse::CertificateRejected;
        });
        auto res = cli.Get(kPath);
        std::printf("Windows, whole chain, as %s: %s (error %#llx)\n", host, accepted ? "accepted" : "refused",
                    static_cast<unsigned long long>(error));
        assert(asked);
        if (std::strcmp(host, "game.supermedo.com") == 0) {
            assert(accepted && res && res->status == 200);
        } else {
            assert(!accepted && !res && res.error() == httplib::Error::SSLServerVerification);
        }
    }
#endif
    {
        // The game's own setup
        httplib::Client cli(kServer);
        cli.enable_server_certificate_verification(true);
        bbnet::TrustWindowsRoots(cli, kServer);
        auto res = cli.Get(kPath);
        std::printf("TrustWindowsRoots: %s\n", res ? std::to_string(res->status).c_str() : httplib::to_string(res.error()).c_str());
        assert(res && res->status == 200);
    }
}

} // namespace

int main() {
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    CheckBundledRoots();
    const char* offline = std::getenv("BB_TEST_OFFLINE");
    if (offline && offline[0] == '1') {
        std::puts("online checks skipped (BB_TEST_OFFLINE=1)");
    } else {
        CheckOnline();
    }
    std::puts("windows trust: ok");
    return 0;
}
