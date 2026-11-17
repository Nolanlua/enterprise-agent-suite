package main

import (
	"context"
	"database/sql"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	_ "github.com/go-sql-driver/mysql"

	"github.com/nolanlua/enterprise-agent-suite/order-service/internal/config"
	"github.com/nolanlua/enterprise-agent-suite/order-service/internal/httpapi"
	"github.com/nolanlua/enterprise-agent-suite/order-service/internal/order"
	"github.com/nolanlua/enterprise-agent-suite/order-service/internal/repository"
	"github.com/nolanlua/enterprise-agent-suite/order-service/internal/supplier"
)

func main() {
	cfg := config.Load()
	db, err := sql.Open("mysql", cfg.MySQLDSN)
	if err != nil {
		log.Fatalf("open mysql: %v", err)
	}
	defer db.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := db.PingContext(ctx); err != nil {
		log.Fatalf("ping mysql: %v", err)
	}
	db.SetMaxOpenConns(40)
	db.SetMaxIdleConns(10)
	db.SetConnMaxLifetime(30 * time.Minute)

	repo := repository.New(db)
	supplierClient := supplier.New(cfg.SupplierURL, cfg.SupplierToken)
	service := order.New(repo, supplierClient)
	handler := httpapi.New(service, cfg.InternalToken)

	server := &http.Server{
		Addr:              cfg.Addr,
		Handler:           handler.Routes(),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      20 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
	go func() {
		log.Printf("order-service listening on %s", cfg.Addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %v", err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()
	_ = server.Shutdown(shutdownCtx)
}
